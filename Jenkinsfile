#!groovy



def getRepoURL() {
  sh "git config --get remote.origin.url > .git/remote-url"
  return readFile(".git/remote-url").trim()
}

def getCommitSha() {
  sh "git rev-parse HEAD > .git/current-commit"
  return readFile(".git/current-commit").trim()
}

void setBuildStatus(String message, String state) {
  step([
      $class: "GitHubCommitStatusSetter",
      reposSource: [$class: "ManuallyEnteredRepositorySource", url: getRepoURL()],
      contextSource: [$class: "ManuallyEnteredCommitContextSource", context: "ci/jenkins/build-status"],
      errorHandlers: [[$class: "ChangingBuildStatusErrorHandler", result: "UNSTABLE"]],
      statusResultSource: [ $class: "ConditionalStatusResultSource", results: [[$class: "AnyBuildResult", message: message, state: state]] ]
  ]);
}


pipeline {
    triggers { pollSCM('*/1 * * * *') }

    options {
        // skipDefaultCheckout(true)  // rather do the checkout in all stages
        // Keep the 10 most recent builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }


    environment {
        REDPITAYA_HOSTNAME = "192.168.178.26"
        //REDPITAYA_HOSTNAME = "rp-f03f3a"
        //REDPITAYA_HOSTNAME = "nobody.justdied.com"
        DOCKER_ARGS = '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
        //NOSETESTS_COMMAND = 'nosetests pyrpl/test/test_ipython_notebook/test_ipython_kernel.py'
        NOSETESTS_COMMAND = 'nosetests'
        PYPI = credentials('f63335ce-493d-4caf-8ebe-d7e2629f79f3')
        REDPITAYA = credentials('2bf38f88-833a-4624-9682-3a6f0a145d30')
        REDPITAYA_USER = "$REDPITAYA_USR"
        REDPITAYA_PASSWORD = "$REDPITAYA_PSW"

    }

    agent any

    stages {
        stage('Notify github that a build was started') {
            agent any
            steps { setBuildStatus("Jenkins build started...", "PENDING") }}
        stage('Unit tests') { parallel {
            stage('Python 3.7') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
                steps { lock('redpitaya') {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            conda list
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND" }}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
            stage('Python 3.6') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.6' }}
                steps { lock('redpitaya') {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            conda list
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
            /*stage('Python 3.5') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.5' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            conda list
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}*/
            stage('Python 2.7') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=2.7' }}
                steps { lock('redpitaya') {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            conda list
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
            stage('Linux binary') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
                steps { lock('fake_redpitaya') {
                    sh  ''' apt-get install psmisc
                            python setup.py install
                            pip install https://github.com/lneuhaus/pyinstaller/tarball/develop
                            pyinstaller pyrpl.spec
                            mv dist/pyrpl ./pyrpl-linux-develop
                            python .deploy_to_sourceforge.py pyrpl-linux-develop
                            chmod 755 pyrpl-linux-develop
                            (./pyrpl-linux-develop config=test_linux hostname=_FAKE_ &)
                            PYRPL_PID=$!
                            sleep 30
                            killall -9 pyrpl-linux-develop
                        '''
                    //sh 'python .deploy_to_sourceforge.py pyrpl-linux-develop'
                    }}
                post { always { archiveArtifacts allowEmptyArchive: true, artifacts: 'pyrpl-linux-develop', fingerprint: true }}}
            stage('pip wheel') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
                steps { lock('fake_redpitaya') {
                    sh  ''' python setup.py install
                            # convert readme file to rst for PyPI
                            conda install pandoc
                            pandoc --from=markdown --to=rst --output=README.rst README.md
                            # make distributions for PyPI
                            python setup.py sdist
                            python setup.py bdist_wheel --universal
                            # upload to PyPI
                            # twine upload dist/**/*.*
                        '''}}
                post { always { archiveArtifacts allowEmptyArchive: true, artifacts: 'dist/**/*.*', fingerprint: true}}}
        }}
        stage('Deploy') {
            agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
                         additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
            when {
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS'}}
            steps {
                sh  ''' python setup.py install
                    '''}}
    }
    post {
        failure {
            emailext (
                attachLog: true,
                subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
                body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
                         <p>Check console output at <a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a></p>""",
                compressLog: false,
                recipientProviders: [requestor(), developers(), brokenTestsSuspects(), brokenBuildSuspects(), upstreamDevelopers(), culprits()],
                replyTo: 'pyrpl.readthedocs.io@gmail.com',
                to: 'pyrpl.readthedocs.io@gmail.com')
            setBuildStatus("Build failed!", "FAILURE")
            }
        success { setBuildStatus("Build successful!", "SUCCESS") }
        unstable { setBuildStatus("Build erroneous!", "ERROR") }
    }
}

