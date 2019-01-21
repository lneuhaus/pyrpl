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
        REDPITAYA_HOSTNAME = "nobody.justdied.com"
        REDPITAYA_USER = "root"
        REDPITAYA_PASSWORD = "Kartoffelschmarn"
    }

    agent none

    stages {
        // git checkout is now done by default
        //stage ("Code pull"){
        //    agent any
        //    steps{
        //      checkout scm
        //        stash 'source'
        //        }}
        stage('Metrics') {
            agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
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
                    sh  ''' radon raw --json pyrpl > raw_report.json
                            radon cc --json pyrpl > cc_report.json
                            radon mi --json pyrpl > mi_report.json
                            sloccount --duplicates --wide pyrpl > sloccount.sc
                        '''
                    //echo "Test coverage"
                    //sh  ''' coverage run pyrpl
                    //        python -m coverage xml -o reports/coverage.xml
                    //    '''
                    echo "Style check"
                    sh  ''' pylint pyrpl || true
                        '''
                }
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
                }}*/
                }
        }}

        stage('Unit tests') { stages {
            stage('Python 3.7') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            python setup.py install
                            nosetests
                            '''}
                post { always { junit allowEmptyResults: true, testResults: 'reports/unit_tests.xml' }}}
            stage('Python 3.6') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.6' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            python setup.py install
                            nosetests
                            '''}
                post { always { junit allowEmptyResults: true, testResults: 'reports/unit_tests.xml' }}}
            /*stage('Python 3.5') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=3.5' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            python setup.py install
                            nosetests
                            '''}
                post { always { junit allowEmptyResults: true, testResults: 'reports/unit_tests.xml' }}}*/
            stage('Python 2.7') {
                agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
                                     additionalBuildArgs  '--build-arg PYTHON_VERSION=2.7' }}
                steps {
                    sh  ''' which python
                            python -V
                            echo $PYTHON_VERSION
                            python setup.py install
                            nosetests
                            '''}
                post { always { junit allowEmptyResults: true, testResults: 'reports/unit_tests.xml' }}}
        }}

        stage('Build and deploy package') {
            agent { dockerfile { args '-u root -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=:0'
                         additionalBuildArgs  '--build-arg PYTHON_VERSION=3.7' }}
            when {
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS'}}
            steps {
                sh  ''' python setup.py install
                        python setup.py bdist_wheel
                        # twine upload dist/*
                    '''
                sh  ''' cd ..
                        git clone https://www.github.com/lneuhaus/pyinstaller.git -b develop
                        cd pyinstaller
                        git status
                        python setup.py develop
                        cd ..
                        cd pyrpl
                        pyinstaller pyrpl.spec
                        mv dist/pyrpl ./pyrpl-linux-develop
                    '''
                //sh 'python .deploy_to_sourceforge.py pyrpl-linux-develop'
                }
            post { always { archiveArtifacts allowEmptyArchive: true, artifacts: 'dist/*whl', fingerprint: true}}}}
        post { failure {
            emailext (
                subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
                body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
                         <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
                recipientProviders: [[$class: 'DevelopersRecipientProvider']],
                to: "pyrpl.readthedocs.io@gmail.com"
                ) }
    }
}

