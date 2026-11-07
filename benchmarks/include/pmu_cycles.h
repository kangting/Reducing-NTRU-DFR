#ifndef CNTRU_PMU_CYCLES_H
#define CNTRU_PMU_CYCLES_H
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <dirent.h>
#include <limits.h>
typedef struct {uint64_t value,enabled,running;} cntru_cycle_reading;
_Static_assert(sizeof(cntru_cycle_reading)==24,"perf read layout");
static int cntru_cycle_fd=-1;
static void cntru_cycle_init(void) {
    const char *inherited=getenv("CNTRU_PERF_FD");
    if(inherited) {
        char *end;long fd=strtol(inherited,&end,10);
        need(*inherited && !*end && fd>=0 && fd<=INT_MAX,"valid scoped PMU fd");
        cntru_cycle_fd=(int)fd;
    } else {
        struct perf_event_attr attr;memset(&attr,0,sizeof(attr));
        attr.type=PERF_TYPE_HARDWARE;attr.size=sizeof(attr);attr.config=PERF_COUNT_HW_CPU_CYCLES;
        attr.pinned=1;attr.exclude_hv=1;
        attr.read_format=PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
        cntru_cycle_fd=(int)syscall(SYS_perf_event_open,&attr,0,-1,-1,PERF_FLAG_FD_CLOEXEC);
        if(cntru_cycle_fd<0)perror("perf_event_open CPU cycles; use the controlled PMU wrapper");
        need(cntru_cycle_fd>=0,"CPU-cycle counter unavailable; no TSC/time conversion fallback");
    }
}
static void cntru_single_task(void) {
    DIR *dir=opendir("/proc/self/task");need(dir!=NULL,"task directory");
    unsigned count=0;struct dirent *entry;
    while((entry=readdir(dir)))if(entry->d_name[0]!='.')count++;
    closedir(dir);need(count==1,"PMU benchmark must have exactly one thread");
    char path[96];snprintf(path,sizeof(path),"/proc/self/task/%ld/children",(long)getpid());
    FILE *children=fopen(path,"r");need(children!=NULL,"children list");
    int c=fgetc(children);fclose(children);need(c==EOF,"PMU benchmark must have no children");
}
static cntru_cycle_reading cntru_read_cycles(void) {
    cntru_cycle_reading reading;
    ssize_t n;do{n=read(cntru_cycle_fd,&reading,sizeof(reading));}while(n<0 && errno==EINTR);
    need(n==(ssize_t)sizeof(reading),"exact PMU read (EOF/error is fatal)");
    __asm__ __volatile__("" : : : "memory");
    return reading;
}
#endif
