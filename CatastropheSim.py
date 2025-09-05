import simpy
import random
import statistics
import collections

# readjustable parameters
LAMBDA = 0.8 # mean arrival rate of processes (processes/sec)
MU = 1.0 # mean service rate of the CPU (processes/sec)
XI = 0.05 # mean rate of catastrophic events (catastrophes/sec)
BETA = 0.2 # mean rate of system restoration (repairs/clsec)
RR_QUANTUM = 0.3 # time quantum for Round-Robin scheduler
SIM_DURATION = 10000000 # total simulation time in seconds

# how we data collect
wait_times = [] # list of all wait times for processes that completed
recovery_times = [] # list of all recovery times after catastrophes (for MTTR calculation)
total_downtime = 0.0 # total downtime due to catastrophes
last_restoration_time = 0.0 # time when the system was last restored
system_operational = True # system starts operational

# this class represents a process within the scheduler
class Process:
    """Represents a process with its attributes."""

    def __init__(self, pid, arrival_time, burst_time): # burst_time is total CPU time needed
        self.pid = pid # process ID
        self.arrival_time = arrival_time # time of arrival
        self.burst_time_initial = burst_time # initial burst time
        self.burst_time_remaining = burst_time # remaining burst time
        self.priority = random.randint(1, 10) # assign a random priority (lower number is higher priority, i.e. 1)

# process generator that is generated according to Poisson Distribution
def process_generator(env, scheduler):
    """Generates processes according to a Poisson process."""
    pid_counter = 0 # process ID counter

    while True: # infinite loop to generate processes
        interarrival_time = random.expovariate(LAMBDA) # time until next arrival
        yield env.timeout(interarrival_time) # wait for that time
        pid_counter += 1 # increment process ID
        burst_time = random.expovariate(MU) # generate burst time
        
        # a process request might be generated, but the system can't accept it until it is operational
        while not system_operational:
            yield env.timeout(0.1) # Wait until the system is back online

        new_process = Process(pid_counter, env.now, burst_time) # create new process
        print(f"Time {env.now:.2f}: [ARRIVAL]   Process {new_process.pid} arrives (burst: {burst_time:.2f}, prio: {new_process.priority})")
        
        scheduler.add_process(new_process) # add process to scheduler

# fault injector that creates catastrophic failures
def fault_injector(env, scheduler):
    """Injects catastrophic failures according to a Poisson process."""
    global system_operational, total_downtime, last_restoration_time # global variables

    while True: # infinite loop to inject faults
        time_to_failure = random.expovariate(XI) # time until next catastrophe (very random)
        yield env.timeout(time_to_failure) # wait for that time

        if system_operational: # only inject fault if system is currently operational
            system_operational = False  # system goes down
            catastrophe_time = env.now # time of catastrophe
            print(f"\n--- Time {catastrophe_time:.2f}: CATASTROPHE OCCURRED ---\n") 
            scheduler.handle_catastrophe() # notify scheduler of catastrophe
            
            repair_duration = random.expovariate(BETA) # time to repair
            yield env.timeout(repair_duration) # wait for repair to complete
            
            total_downtime += repair_duration # accumulate total downtime
            system_operational = True # system is back up
            last_restoration_time = env.now # time of restoration
            scheduler.is_recovering = True # mark scheduler as recovering
            print(f"\n--- Time {env.now:.2f}: System RESTORED (downtime: {repair_duration:.2f}s) ---\n") 

# base class for schedulers
class Scheduler:

    """Base class for a CPU scheduler."""
    def __init__(self, env): # initialize with simpy environment
        self.env = env # simpy environment
        self.running_process_event = None # currently running process event
        self.is_recovering = False # flag for recovery state
        self.active_processes = {} # track active processes
        env.process(self.run()) # start the scheduler's main run loop

    # abstract method to add a process to the scheduler
    def add_process(self, process): 
        raise NotImplementedError # must be implemented by subclasses
    
    # abstract method for the main run loop of the scheduler
    def run(self):
        raise NotImplementedError # must be implemented by subclasses
    
    # handle catastrophe event
    def handle_catastrophe(self):
        if self.running_process_event and not self.running_process_event.triggered: # if a process is running
            self.running_process_event.interrupt("catastrophe") # interrupt it
        self.is_recovering = False # reset recovery flag
        print("Scheduler: All processes in queue lost due to catastrophe.") # log message

# non-preemptive scheduler base class (different from preemptive ones)
# we have this because the way we serve processes is different
class NonPreemptiveScheduler(Scheduler):

    def __init__(self, env): # initialize with simpy environment
        super().__init__(env) # call base class initializer
        self.cpu = simpy.Resource(env, capacity=1) # single CPU resource

    # main run loop for non-preemptive schedulers
    def run(self):

        while True:
            if not system_operational: # do not schedule if system is down
                yield self.env.timeout(0.1) # wait a bit before checking again
                continue # skip to next iteration

            if self.is_recovering and self.cpu.count == 0 and len(self.ready_queue.items) == 0: # if recovering and CPU idle and no processes
                recovery_time = self.env.now - last_restoration_time # calculate recovery time
                if recovery_time > 1e-6: # avoid tiny float errors
                    recovery_times.append(recovery_time) # log recovery time
                self.is_recovering = False # reset recovery flag

            item = yield self.ready_queue.get() # get next process from ready queue
            process = getattr(item, 'item', item) # handle PriorityItem or direct Process
            
            self.running_process_event = self.env.process(self.serve_process(process)) # serve the process
            try: 
                yield self.running_process_event # wait for it to finish
            except simpy.Interrupt as i: 
                if i.cause == "catastrophe": # if interrupted due to catastrophe
                    print(f"Time {self.env.now:.2f}: [INTERRUPT] Process {process.pid} was interrupted by a fault.")

    # serve a process (non-preemptive)
    def serve_process(self, process):

        with self.cpu.request() as req: # request CPU
            yield req # wait for CPU
            start_time = self.env.now # record start time
            wait_time = start_time - process.arrival_time # calculate wait time
            wait_times.append(wait_time) # log wait time

            print(f"Time {start_time:.2f}: [EXECUTE]   Process {process.pid} starts (waited: {wait_time:.2f}s)") # log execution start
            yield self.env.timeout(process.burst_time_initial) # run for the entire burst time
            print(f"Time {self.env.now:.2f}: [COMPLETE]  Process {process.pid} finished.") # log completion

# specific FCFS Scheduler implementation
class FCFS_Scheduler(NonPreemptiveScheduler):

    def __init__(self, env): # initialize with simpy environment
        super().__init__(env) # call base class initializer
        self.ready_queue = simpy.Store(env) # FIFO queue for processes

    def add_process(self, process): self.ready_queue.put(process) # add process to ready queue

    def handle_catastrophe(self): # handle catastrophe event
        super().handle_catastrophe() # call base class handler
        self.ready_queue = simpy.Store(self.env) # reset ready queue

# specific SJF Scheduler implementation
class SJF_Scheduler(NonPreemptiveScheduler):

    def __init__(self, env): # initialize with simpy environment
        super().__init__(env) # call base class initializer
        self.ready_queue = simpy.PriorityStore(env) # priority queue for processes

    def add_process(self, process): 
        self.ready_queue.put(simpy.PriorityItem(process.burst_time_initial, process)) # add process with burst time as priority

    def handle_catastrophe(self): # handle catastrophe event
        super().handle_catastrophe() # call base class handler
        self.ready_queue = simpy.PriorityStore(self.env) # reset priority queue

# specific Round-Robin Scheduler implementation
class RR_Scheduler(Scheduler):

    def __init__(self, env): # initialize with simpy environment
        super().__init__(env) # call base class initializer
        self.cpu = simpy.Resource(env, capacity=1) # single CPU resource
        self.ready_queue = collections.deque() # FIFO queue using a deque

    def add_process(self, process): 
        self.ready_queue.append(process) # add process to the end of the queue

    def handle_catastrophe(self): # handle catastrophe event
        super().handle_catastrophe() # call base class handler
        self.ready_queue.clear() # clear the ready queue

    def run(self): # main run loop for the scheduler
        while True: # infinite loop to schedule processes
            if not system_operational: # do not schedule if system is down
                yield self.env.timeout(0.1) # wait a bit before checking again
                continue # skip to next iteration

            if self.is_recovering and self.cpu.count == 0 and not self.ready_queue: # if recovering and CPU idle and no processes
                recovery_time = self.env.now - last_restoration_time # calculate recovery time
                
                if recovery_time > 1e-6: # avoid tiny float errors
                    recovery_times.append(recovery_time) # log recovery time
                self.is_recovering = False # reset recovery flag
            
            if not self.ready_queue: # if the ready queue is empty
                yield self.env.timeout(0.01) # wait for a short time
                continue # skip to next iteration

            process = self.ready_queue.popleft() # get the next process from the front of the queue
            self.running_process_event = self.env.process(self.serve_process(process)) # serve the process

            try:
                yield self.running_process_event # wait for it to finish or be preempted

            except simpy.Interrupt as i:
                 if i.cause == "catastrophe": # if interrupted due to catastrophe
                    print(f"Time {self.env.now:.2f}: [INTERRUPT] Process {process.pid} interrupted by fault.")
    
    def serve_process(self, process): # serves a single process for a time quantum
        with self.cpu.request() as req: # request CPU
            yield req # wait for CPU
            if process.burst_time_remaining == process.burst_time_initial: # if this is the first time the process runs
                 wait_time = self.env.now - process.arrival_time # calculate wait time
                 wait_times.append(wait_time) # log wait time
                 print(f"Time {self.env.now:.2f}: [EXECUTE]   Process {process.pid} starts (waited: {wait_time:.2f}s)")
            else: # if the process is resuming after preemption
                 print(f"Time {self.env.now:.2f}: [RESUME]    Process {process.pid} resumes.")
            time_to_run = min(RR_QUANTUM, process.burst_time_remaining) # determine time slice (quantum or remaining time)
            yield self.env.timeout(time_to_run) # run for the determined time slice
            process.burst_time_remaining -= time_to_run # update remaining burst time
            if process.burst_time_remaining > 0: # if process is not finished
                print(f"Time {self.env.now:.2f}: [PREEMPT]   Process {process.pid} preempted (rem: {process.burst_time_remaining:.2f})")
                self.ready_queue.append(process) # add it back to the end of the queue
            else: # if process is finished
                print(f"Time {self.env.now:.2f}: [COMPLETE]  Process {process.pid} finished.")

# specific Preemptive Priority Scheduler implementation
class Preemptive_Priority_Scheduler(Scheduler):
    def __init__(self, env): # initialize with simpy environment
        super().__init__(env) # call base class initializer
        self.cpu = simpy.PreemptiveResource(env, capacity=1) # preemptive CPU resource
        self.ready_queue = collections.deque() # use a deque to keep track of active processes

    def add_process(self, process): # add a new process to the system
        # a new process might need to preempt the current one
        # we model this by having the new process request the CPU immediately
        self.ready_queue.append(process) # add process to our tracking deque
        self.env.process(self.serve_process(process)) # create a new simpy process to manage its execution

    def handle_catastrophe(self): # handle catastrophe event
        # Interrupt all active processes being served
        for process_event in self.active_processes.values():
            if not process_event.triggered:
                process_event.interrupt("catastrophe")
        
        super().handle_catastrophe() # call base class handler
        self.ready_queue.clear() # clear the ready queue

    def run(self): # main run loop for the scheduler
         # this loop is mainly for MTTR calculation now
         # since serve_process is initiated by add_process
        while True: # infinite loop
            if not system_operational: # do not schedule if system is down
                yield self.env.timeout(0.1) # wait a bit before checking again
                continue # skip to next iteration

            if self.is_recovering and self.cpu.count == 0 and not self.ready_queue: # if recovering and CPU idle and no processes
                recovery_time = self.env.now - last_restoration_time # calculate recovery time
                if recovery_time > 1e-6: # avoid tiny float errors
                    recovery_times.append(recovery_time) # log recovery time
                self.is_recovering = False # reset recovery flag
            yield self.env.timeout(0.1) # check periodically

    def serve_process(self, process): # serves a single process, can be preempted
        start_wait = self.env.now # record time when process starts waiting for CPU
        
        try:
            with self.cpu.request(priority=process.priority) as req: # request CPU with a certain priority
                self.active_processes[process.pid] = self.env.active_process
                
                yield req # wait for the CPU (may preempt another process)
                
                del self.active_processes[process.pid]
                
                wait_time = self.env.now - start_wait # calculate total wait time
                wait_times.append(wait_time) # log wait time
                
                print(f"Time {self.env.now:.2f}: [EXECUTE]   Process {process.pid} starts (waited: {wait_time:.2f}s)")
                
                start_exec_time = self.env.now # record when execution actually starts
                yield self.env.timeout(process.burst_time_remaining) # attempt to run for its entire remaining time
                
                print(f"Time {self.env.now:.2f}: [COMPLETE]  Process {process.pid} finished.")
                if process in self.ready_queue:
                    self.ready_queue.remove(process) # remove from deque upon completion

        except simpy.Interrupt as i: # handles interruptions
            if process.pid in self.active_processes:
                del self.active_processes[process.pid]

            if i.cause == "catastrophe": # if interrupted by a catastrophe
                print(f"Time {self.env.now:.2f}: [INTERRUPT] Process {process.pid} interrupted by fault.")
                return # end this process's execution

            # interrupted by a higher-priority process
            time_spent_executing = self.env.now - start_exec_time # calculate time it actually ran for
            process.burst_time_remaining -= time_spent_executing # update remaining time
            print(f"Time {self.env.now:.2f}: [PREEMPT] Process {process.pid} preempted by higher priority process (rem: {process.burst_time_remaining:.2f}s).")
            # The process remains in the queue. The preempting process's 'serve_process' has taken over.

# simulation setup
if __name__ == "__main__":
    print("Starting CPU Scheduler Simulation...")
    env = simpy.Environment() # create a simpy environment
    
    # CHOOSE SIMULATOR TO RUN HERE (UNCOMMENT)
    # scheduler = FCFS_Scheduler(env)
    # scheduler = SJF_Scheduler(env)
    # scheduler = Preemptive_Priority_Scheduler(env)
    scheduler = RR_Scheduler(env)
    
    env.process(process_generator(env, scheduler)) # start the process generator
    env.process(fault_injector(env, scheduler)) # start the fault injector

    env.run(until=SIM_DURATION) # run the simulation for the specified duration

    # results Analysis
    print("\n" + "="*40)
    print("--- SIMULATION FINISHED: FINAL METRICS ---")
    print("="*40)

    if wait_times: # check if any processes completed
        avg_wait_time = statistics.mean(wait_times) # calculate the average wait time
        print(f"Average Waiting Time: {avg_wait_time:.2f} s")
    else: # if no processes completed
        print("Average Waiting Time: N/A (No processes completed)")

    availability = ((SIM_DURATION - total_downtime) / SIM_DURATION) * 100 # calculate system availability
    print(f"System Availability: {availability:.2f}%")

    if recovery_times: # check if any recovery events occurred
        mttr = statistics.mean(recovery_times) # calculate the mean time to recovery
        print(f"Mean Time To Recovery (MTTR): {mttr:.2f} s")
    else: # if no recovery events were measured
        print("Mean Time To Recovery (MTTR): N/A (No recovery events were measured)")
    print("="*40 + "\n")