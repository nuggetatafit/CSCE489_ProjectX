# Discrete-Simulation: A Catastrophe Queueing Framework for Analyzing Reliable CPU Schedulers

**By 2d Lt Nathaniel Vinoya**

**CSCE489 - Project X**

**05 September 2025**

------------------

## Introduction

This project is a supplementary discrete-event simulation to analyze the performance of CPU scheduling algorithms in an environment prone to catastrophic failures. This uses the `SimPy` library in Python to model the stochastic nature of process arrivals, service time, system failures, and restoration times, with the aim to measure each scheduler's reliability and efficiency.

------------------

## Components of `CatastropheSim.py`

`Process` - A class representing process attributes like arrival time (which is Poisson-distributed) and CPU burst time (which is exponentially-distributed)

`process_generator` - Creates new processes according to Poisson process to model random arrivals

`fault_injector` - Injects system failures according to Poisson process to model random intervals

`Scheduler` - Abstract base class to define core interfaces for all schedulers

`FCFS_Scheduler` - Implements FCFS queue as FIFO queue

`SJF_Scheduler` - Implements SJF queue as a min-heap

`RR_Scheduler` - Implements the RR queue as an adjusted FIFO queue with time slices

`Preemptive_Priority_Scheduler` - Implements preemptive-priority queue as min-heap based on randomly assigned priority levels

------------------

## How to Use

You can use this repository by doing the following:

1. Ensure that you have Python3 and `SimPy` library downloaded: `pip install simpy`
2. Open `CatstropheSim.py`
3. If desired, you can adjust the global paramters `LAMBDA`, `MU`, `XI`, `BETA`, `RR_QUANTUM`, `SIM_DURATION`
4. Select a scheduler in the bottom of the script by uncommenting which scheduler you would like to choose, i.e. `scheduler = FCFS_Scheduler(env)`
5. Execute `python3 CatastropheSim.py`

The metrics that would be outputted include the Average Waiting Time, System Availability, and MTTR.

------------------

## Limitations

In the provided script, I mainly used sample arrival, service, recovery, and catastrophe rates. With further research on the application of these schedulers, it can be adjusted to be more realistic to how they are applied in real-world scheduling. Furthermore, the catastrophe rates can also consider systems with varying levels of reliability and failure, given that certain operating systems tend to fail differently than others (i.e. an older system would likely undergo Kernel Panic more often).

------------------

## Final Note

If you have any questions, comments, or concerns, feel free to contact me through the following means:

**AU Teams:** nathaniel.vinoya.1@au.af.edu

**.mil Email:** nathaniel.vinoya.1@us.af.mil

**AFIT Email:** nathaniel.vinoya@afit.edu

------------------

## References

[SimPy](https://simpy.readthedocs.io/en/latest/)

[GeeksforGeeks SimPy](https://www.geeksforgeeks.org/python/basics-of-discrete-event-simulation-using-simpy/)

[Medium SimPy](https://medium.com/@vitostamatti1995/introduction-to-discrete-event-simulation-with-python-3b0cce67f92e)

[Operating System Concepts 9th Ed](https://drive.google.com/file/d/1AFRyycszmrdGeOywOkMrV1CxjNg0Qj7P/view?usp=sharing)
