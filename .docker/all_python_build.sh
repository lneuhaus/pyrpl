docker system prune -a
docker build --build-arg PYTHON_VERSION=3.7 -t python-37 ../.
docker build --build-arg PYTHON_VERSION=3.6 -t python-36 ../.
docker build --build-arg PYTHON_VERSION=3.5 -t python-35 ../.
docker build --build-arg PYTHON_VERSION=2.7 -t python-27 ../.
docker build --build-arg PYTHON_VERSION=3 -t python-3 ../.
docker build -t python ../.
