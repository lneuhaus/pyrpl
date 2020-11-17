docker run -ti --rm \
       -e DISPLAY \
       -v /tmp/.X11-unix:/tmp/.X11-unix \
       -v /home/leo/github/pyrpl:/home/pyrpl \
       -v /home/leo/github/pyrpl-copy:/home/pyrpl-copy \
       --net=host \
       python-35
