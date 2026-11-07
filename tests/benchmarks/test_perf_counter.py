"""Counter protocol tests use synthetic fds; no fixture is a PMU result."""
import array
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import subprocess
import threading
import hashlib
import unittest
from unittest.mock import patch

import perf_counter as perf


class PerfCounterTests(unittest.TestCase):
    def test_attr_is_single_task_pinned_raw_cpu_cycles(self):
        kind,size,config,period,sample,fmt,flags,*_=struct.unpack('=IIQQQQQIIQ',perf.ATTR)
        self.assertEqual((kind,size,config,period,sample,fmt),(0,64,0,0,0,3))
        self.assertEqual(flags,4|64)  # pinned, exclude_hv; no inherit or kernel exclusion.

    def test_scm_rights_transfers_one_fd(self):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        try:
            with tempfile.TemporaryFile() as f:
                f.write(b'synthetic');f.seek(0)
                left.sendmsg([b'CPU_CYCLES_V1'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[f.fileno()]))])
                fd=perf.recv_fd(right)
                try:self.assertEqual(os.read(fd,9),b'synthetic')
                finally:os.close(fd)
        finally:left.close();right.close()

    def test_missing_or_wrong_response_cannot_be_a_counter(self):
        for data in (b'CPU_CYCLES_V1',b'TSC_TICKS'):
            left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
            try:
                left.send(data)
                with self.assertRaises(RuntimeError):perf.recv_fd(right)
            finally:left.close();right.close()

    def test_unrelated_pid_is_rejected_before_open(self):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        try:
            left.send(json.dumps({'pid':os.getpid(),'executable':'/bin/true'}).encode())
            with patch.object(perf,'open_counter') as opened:
                with self.assertRaisesRegex(RuntimeError,'comparator single-thread'):
                    perf.serve_request(right,-1,os.getuid(),Path('/synthetic-repo'))
                opened.assert_not_called()
        finally:left.close();right.close()

    def test_same_pid_exec_receives_scoped_fd_end_to_end(self):
        # Real socket/fork/exec/SCM_RIGHTS path with deliberately synthetic data.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryFile() as counter:
            repository=Path(d);dest=repository/'benchmarks/build/synthetic';dest.mkdir(parents=True)
            source=repository/'fixture.c';executable=dest/'bench'
            source.write_text(r'''#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
int main(void){uint64_t x[3];int fd=atoi(getenv("CNTRU_PERF_FD"));
if(read(fd,x,sizeof(x))!=sizeof(x))return 2;
printf("%ld %llu\n",(long)getpid(),(unsigned long long)x[0]);return 0;}
''')
            subprocess.run(['gcc',str(source),'-o',str(executable)],check=True,capture_output=True)
            digest=hashlib.sha256(executable.read_bytes()).hexdigest()
            (dest/'build.json').write_text(json.dumps({'binary_sha256':digest}))
            counter.write(struct.pack('=QQQ',42,100,100));counter.seek(0)
            broker,client=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
            responses=[];errors=[]
            def serve():
                try:responses.append(perf.serve_request(broker,os.getpid(),os.getuid(),repository))
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=serve)
            try:
                with patch.object(perf,'open_counter',side_effect=lambda pid:os.dup(counter.fileno())), \
                     patch.dict(os.environ,{'CNTRU_PERF_BROKER_FD':str(client.fileno())}):
                    thread.start()
                    result=perf.run_benchmark([str(executable)],capture_output=True,text=True,timeout=10)
                    thread.join(10)
                self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
                self.assertEqual(result.returncode,0,result.stderr)
                pid,value=map(int,result.stdout.split())
                self.assertEqual((pid,value),(responses[0]['pid'],42))
                self.assertEqual(responses[0]['binary_sha256'],digest)
            finally:broker.close();client.close()

    def test_only_timed_child_receives_broker(self):
        with patch.dict(os.environ,{'CNTRU_PERF_BROKER_FD':'123'}),patch.object(perf.subprocess,'run') as run:
            perf.run_benchmark(['/synthetic/bench','1','32'],timeout=1)
            args,kwargs=run.call_args
            self.assertEqual(kwargs['pass_fds'],(123,))
            self.assertEqual(args[0][-3:],['/synthetic/bench','1','32'])


if __name__=='__main__':unittest.main()
