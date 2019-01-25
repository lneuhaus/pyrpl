#!groovy


pipeline {
    triggers { pollSCM('*/1 * * * *') }

    options {
        // skipDefaultCheckout(true)  // rather do the checkout in all stages
        // Keep the 10 most recent builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        // lock the redpitaya such that no two pipelines running in parallel can interfere
        lock('redpitaya')
    }


    environment {
        REDPITAYA_HOSTNAME = "192.168.178.26"
        //REDPITAYA_HOSTNAME = "rp-f03f3a"
        //REDPITAYA_HOSTNAME = "nobody.justdied.com"
        REDPITAYA_USER = "root"
        REDPITAYA_PASSWORD = "Kartoffelschmarn"
        DOCKER_ARGS = '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
        //NOSETESTS_COMMAND = 'nosetests pyrpl/test/test_ipython_notebook/test_ipython_kernel.py'
        NOSETESTS_COMMAND = 'nosetests'
    }

    agent none

    stages {
        /*
        stage('Metrics') {
            agent { dockerfile { args "$DOCKER_ARGS"
                                 additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
            stages {
                stage('Docker environment diagnostics') { steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            '''
                }}
                stage('Install') { steps {
                    sh 'python setup.py install'
                }}
                stage('Static code metrics') { steps {
                    echo "Raw metrics"
                    //sh  ''' radon raw --json pyrpl > raw_report.json
                    //        radon cc --json pyrpl > cc_report.json
                    //        radon mi --json pyrpl > mi_report.json
                    //        sloccount --duplicates --wide pyrpl > sloccount.sc
                    //    '''
                    //echo "Test coverage"
                    //sh  ''' coverage run pyrpl
                    //        python -m coverage xml -o reports/coverage.xml
                    //    '''
                    //echo "Style check"
                    //sh  ''' pylint pyrpl || true
                    //    '''
                }
                */
                /*post{ always { step(
                    [ $class: 'CoberturaPublisher',
                               autoUpdateHealth: false,
                               autoUpdateStability: false,
                               coberturaReportFile: 'reports/coverage.xml',
                               failNoReports: false,
                               failUnhealthy: false,
                               failUnstable: false,
                               maxNumberOfBuilds: 10,
                               onlyStable: false,
                               sourceEncoding: 'ASCII',
                               zoomCoverageChart: false])
                }}*/ /*
                }
        }} */
        stage('Notify github') { steps {
            githubNotify credentialsId: "$myvariable", description: 'Jenkins has started...', status: 'PENDING', account: 'lneuhaus', repo: 'pyrpl', gitApiUrl: 'https://api.github.com'
        }}
        stage('Unit tests') { stages {
            stage('Python 3.7') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
            stage('Python 3.6') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.6' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
            /*stage('Python 3.5') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.5' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}*/
            stage('Python 2.7') {
                agent { dockerfile { args "$DOCKER_ARGS"
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=2.7' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            # use a custom global configfile adapted to the hardware for unit tests
                            cp ./jenkins_global_config.yml ./pyrpl/config/global_config.yml
                            python setup.py install
                        '''
                    sh "$NOSETESTS_COMMAND"}
                post { always { junit allowEmptyResults: true, testResults: 'unit_test_results.xml' }}}
        }}

        stage('Build and deploy package') {
            agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0 --net=host'
                         additionalBuildArgs  '--build-arg PYTHON_VERSION=3.6' }}
            when {
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS'}}
            steps {
                sh  ''' python setup.py install
                        python setup.py bdist_wheel
                        # twine upload dist/*
                    '''
                sh  ''' pip install pyinstaller
                        pyinstaller pyrpl.spec
                        mv dist/pyrpl ./pyrpl-linux-develop
                    '''
                //sh 'python .deploy_to_sourceforge.py pyrpl-linux-develop'
                }
            post { always { archiveArtifacts allowEmptyArchive: true, artifacts: 'dist/*whl, pyrpl-linux-develop', fingerprint: true}}}}
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
                //githubNotify description: 'Jenkins build has failed!',  status: 'FAILURE'
                }
            //success {
            //    githubNotify description: 'Jenkins build was successful!',  status: 'SUCCESS' }
            //unstable {
            //    githubNotify description: 'Error in jenkins build!',  status: 'ERROR' }
        }
}

