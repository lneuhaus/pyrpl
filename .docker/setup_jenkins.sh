#!/bin/bash

echo 'JAVA_ARGS="-Dhudson.tasks.MailSender.SEND_TO_UNKNOWN_USERS=true"' >> /etc/default/jenkins
xhost +local:docker

