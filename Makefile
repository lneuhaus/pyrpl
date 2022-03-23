SRC_DIR=.

all: clean sloc test flakes lint clone

# almost direct translation of travis script
before_install:
	apt-get update;
	if [[ "$TRAVIS_OS_NAME" == "linux" && "$TRAVIS_PYTHON_VERSION" == "2.7" ]]; then
	wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -O miniconda.sh;
	elif [[ "$TRAVIS_OS_NAME" == "linux" ]]; then
	wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh;
	elif [[ "$TRAVIS_OS_NAME" == "osx" && "$TRAVIS_PYTHON_VERSION" == "2.7" ]]; then
	wget https://repo.continuum.io/miniconda/Miniconda2-latest-MacOSX-x86_64.sh -O miniconda.sh;
	elif [[ "$TRAVIS_OS_NAME" == "osx" ]]; then
	wget https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -O miniconda.sh;
	else
	echo "Invalid combination of OS ($TRAVIS_OS_NAME) and Python version ($TRAVIS_PYTHON_VERSION)";
	fi
	chmod +x miniconda.sh
	bash miniconda.sh -b -p $HOME/miniconda
	export PATH="$HOME/miniconda/bin:$PATH"
	hash -r
	conda config --set always_yes yes --set changeps1 no
	conda update -q conda
	# Useful for debugging any issues with conda
	conda info -a
	# The next lines fix a crash with multiprocessing on Travis and are not specific to using Miniconda
	sudo rm -rf /dev/shm
	sudo ln -s /run/shm /dev/shm
	# starts gui support, see https://docs.travis-ci.com/user/gui-and-headless-browsers/
	# and https://github.com/travis-ci/travis-ci/issues/7313#issuecomment-279914149 (for MacOSX)
	# formerly "sh -e sudo Xvfb :99 -ac -screen 0 1024x768x8";
	export DISPLAY=":99.0"
	if [[ "$TRAVIS_OS_NAME" == "linux" ]]; then
	sh -e /etc/init.d/xvfb start;
	fi
	if [[ "$TRAVIS_OS_NAME" == "osx" ]]; then
	Xvfb :98 -ac -screen 0 1024x768x8;
	fi &
	# give it some time to start
	sleep 3
	conda create -q -n test-environment python=$TRAVIS_PYTHON_VERSION numpy scipy paramiko pandas nose pip pyqt qtpy
	source activate test-environment
	# convert readme file to rst for PyPI
	conda install pandoc
	pandoc --from=markdown --to=rst --output=README.rst README.md
	# overwrite default global config file with a custom one for travis (allows slower communication time)
	\cp ./travis_global_config.yml ./pyrpl/config/global_config.yml
	# packages for coverage reports
	conda install --yes -c conda-forge coveralls
	pip install coverage codecov
	# install pyrpl
	python setup.py install

script:
	if [[ "$TRAVIS_PYTHON_VERSION" == "3.5" && "$TRAVIS_OS_NAME" == "osx" ]]; then
	cd ..;
	git clone https://www.github.com/lneuhaus/pyinstaller.git -b develop;
	cd pyinstaller;
	git status;
	python setup.py develop;
	cd ..;
	cd pyrpl;
	pyinstaller pyrpl.spec;
	mv dist/pyrpl ./pyrpl-mac-develop;
	python .deploy_to_sourceforge.py pyrpl-mac-develop;
	chmod 755 pyrpl-mac-develop;
	(./pyrpl-mac-develop config=test_osx hostname=_FAKE_ &);
	PYRPL_PID=$!;
	sleep 30;
	killall -9 pyrpl-mac-develop;
	fi
	if [[ "$TRAVIS_PYTHON_VERSION" == "3.4" && "$TRAVIS_OS_NAME" == "linux" ]]; then
	cd ..;
	git clone https://www.github.com/lneuhaus/pyinstaller.git -b develop;
	cd pyinstaller;
	git status;
	python setup.py develop;
	cd ..;
	cd pyrpl;
	pyinstaller pyrpl.spec;
	mv dist/pyrpl ./pyrpl-linux-develop;
	python .deploy_to_sourceforge.py pyrpl-linux-develop;
	chmod 755 pyrpl-linux-develop;
	(./pyrpl-linux-develop config=test_linux hostname=_FAKE_ &);
	PYRPL_PID=$!;
	sleep 30;
	killall pyrpl-linux-develop;
	fi
	- if [[ "$TRAVIS_PYTHON_VERSION" == "2.7" &&  "$TRAVIS_OS_NAME" == "linux" ]] || [[ "$TRAVIS_PYTHON_VERSION" == "3.5" &&  "$TRAVIS_OS_NAME" == "osx" ]] || [[ "$TRAVIS_PYTHON_VERSION" == "3.6" && "$TRAVIS_OS_NAME" == "linux" ]]; then
	echo "NOSETESTS ARE ENABLED";
	nosetests;
	fi

after_script:
	if [[ "$TRAVIS_PYTHON_VERSION" == "2.7" &&  "$TRAVIS_OS_NAME" == "linux" ]] || [[ "$TRAVIS_PYTHON_VERSION" == "3.5" &&  "$TRAVIS_OS_NAME" == "linux" ]] || [[ "$TRAVIS_PYTHON_VERSION" == "3.6" && "$TRAVIS_OS_NAME" == "osx" ]]; then
	codecov;
	fi

# automatic release when a new tag is created: before_deploy, deploy, and after_deploy
before_deploy:
	echo Deploy
	source activate test-environment

deploy:
	provider: pypi
	user: lneuhaus
	password: $PYPI_PASSWORD
	skip_cleanup: true
	on:
	  tags: true

distributions: "sdist bdist_wheel --universal"

# make an executable for linux and upload to sourceforge in python 3.4
# same for macos
# put windows executable into the right directory (at last such that "latest" points to windows .exe)
after_deploy:
	source activate test-environment
	if [[ "$TRAVIS_PYTHON_VERSION" == "3.5" && "$TRAVIS_OS_NAME" == "linux" && "$TRAVIS_TEST_RESULT" == 0 ]]; then
	pip install https://github.com/pyinstaller/pyinstaller/archive/develop.zip;
	export QT_QPA_PLATFORM_PLUGIN_PATH=$HOME/miniconda/envs/test-environment/plugins/platforms;
	pyinstaller pyrpl.spec;
	mv dist/pyrpl ./pyrpl-linux;
	python .deploy_to_sourceforge.py pyrpl-linux;
	fi
	if [[ "$TRAVIS_PYTHON_VERSION" == "3.5" && "$TRAVIS_OS_NAME" == "osx" && "$TRAVIS_TEST_RESULT" == 0 ]]; then
	pip install https://github.com/pyinstaller/pyinstaller/archive/develop.zip;
	export QT_QPA_PLATFORM_PLUGIN_PATH=$HOME/miniconda/envs/test-environment/plugins/platforms;
	pyinstaller pyrpl.spec;
	mv dist/pyrpl ./pyrpl-mac;
	python .deploy_to_sourceforge.py pyrpl-mac;
	fi
	wget wget https://sourceforge.net/projects/pyrpl/files/pyrpl-windows.exe -O pyrpl-windows.exe
	python .deploy_to_sourceforge.py pyrpl-windows.exe
	
sloc:
	sloccount --duplicates --wide --details $(SRC_DIR) | fgrep -v .git > sloccount.sc || :

test:
	cd $(SRC_DIR) && nosetests --verbose --with-xunit --xunit-file=../xunit.xml --with-xcoverage --xcoverage-file=../coverage.xml || :

flakes:
	find $(SRC_DIR) -name *.py|egrep -v '^./tests/'|xargs pyflakes  > pyflakes.log || :

lint:
	find $(SRC_DIR) -name *.py|egrep -v '^./tests/' | xargs pylint --output-format=parseable --reports=y > pylint.log || :

clone:
	clonedigger --cpd-output $(SRC_DIR) || :

clean:
	rm -f pyflakes.log
	rm -f pylint.log
	rm -f sloccount.sc
	rm -f output.xml
	rm -f coverage.xml
	rm -f xunit.xml
