monitor_server.c: instantiate the /dev/mem mapping only once to accelerate the execution time (should gain a few 10-100 microseconds per request)

