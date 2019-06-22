 /* COPYRIGHT NOTICE OF MONITOR.C 
 * $Id$
 *
 * @brief Simple program to read/write from/to any location in memory.
 *
 * @Author Crt Valentincic <crt.valentincic@redpitaya.com>
 *         
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 * This part of code is written in C programming language.
 * Please visit http://en.wikipedia.org/wiki/C_(programming_language)
 * for more details on the language used herein.
 */
/*
###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2018  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
############################################################################### 
 */


/* 
Communication protocol for the data server:

The program is launched on the redpitaya with 

./monitor-server PORT-NUMBER AUTH-TOKEN

where
- the default port number is 2222, and
- the 32-hex-characters auth-token is by default 32 times '0'.

We allow for bidirectional data transfer. The client (python program) connects
to the server, which in return accepts the connection. The server then forks
such that one server process waits for new incoming connections and the other
one executes the sequence detailed below. To make sure that the
client connects to the right server, the client must initially send the
32-character authentification token. It the wrong token was sent, the server
closes the connection. If the right token was sent, the following protocol is
executed indefinitely.

The client sends 8 bytes of data:
- Byte 1 is interpreted as a character: 'r' for read and 'w' for write, and 'c' for close.
  All other messages are ignored.
- Byte 2 is reserved.
- Bytes 3+4 are interpreted as unsigned int. This number n is the amount of 4-byte-units
  to be read or written. The maximum is 2^16 blocks of 4 bytes each.
- Bytes 5-8 are the start address to be written to or read from.

- If the command is read, the server will then send the requested 4*n bytes to the client.
- If the command is write, the server will wait for 4*n bytes of data from the server and
  write them to the designated FPGA address space.
- If the command is close, or if the connection is broken, the server program will terminate.

After this, the server will wait for the next command. 
*/
 
 /* for now the program is utterly unoptimized... */
 
#define _GNU_SOURCE


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <stdint.h>
#include <sys/socket.h>
#include <netinet/in.h>

void error(const char *msg);

#define FATAL do { fprintf(stderr,"Error at line %d, file %s (%d) [%s]\n", __LINE__, __FILE__, errno, strerror(errno)); \
									error("FATAL ERROR"); exit(1); } while(0)
 
//#define MAP_SIZE 4096UL
//#define MAP_SIZE 65536UL
#define MAP_SIZE 131072UL
//allowed address space: 0x40000000 to 0x40800000 has size 0x800000 = 128*65536 = 8388608
//#define MAP_SIZE 8388608UL
#define MAP_MASK (MAP_SIZE - 1)
#define MAX_LENGTH 65535

#define DEBUG_MONITOR 0

unsigned long read_value(unsigned long a_addr);
unsigned long* read_values(unsigned long a_addr, unsigned long* a_values_buffer, unsigned long a_len);
void write_value(unsigned long a_addr, unsigned long a_value);
void write_values(unsigned long a_addr, unsigned long* a_values, unsigned long a_len);

//FPGA memory handlers
void* map_base = (void*)(-1);
int fd = -1;

//sockets are globally defined for error handling
int sockfd;
int newsockfd;

//open and close memory mapping to FPGA registers
void open_map_base() {
    int addr = 0x40000000;
    if((fd = open("/dev/mem", O_RDWR | O_SYNC)) == -1) FATAL;
    map_base = mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, addr & ~MAP_MASK);
	if(map_base == (void *) -1) FATAL;
}

void close_map_base() {
	/*if (map_base != (void*)(-1)) {
		if(munmap(map_base, MAP_SIZE) == -1) FATAL;
		map_base = (void*)(-1);
	}
	if (fd != -1) {
		close(fd);
	}
	*/;
}
/*
//basic read and write operations
unsigned long* read_values(unsigned long a_addr, unsigned long* a_values_buffer, unsigned long a_len) {
	unsigned long* virt_addr = map_base + (a_addr & MAP_MASK);
	unsigned long i;
	printf("address to read %d",(int)a_addr);
	for (i = 0; i < a_len; i++) {;
		a_values_buffer[i] = virt_addr[i];
	}
	return a_values_buffer;
}

void write_values(unsigned long a_addr, unsigned long* a_values, unsigned long a_len) {
	void* virt_addr = map_base + (a_addr & MAP_MASK);
	unsigned long i;
	for (i = 0; i < a_len; i++) {
		((unsigned long *) virt_addr)[i] = a_values[i];
	}
}
*/

/* server process and error handling */

void error(const char *msg)
{
    perror(msg);
    close(newsockfd); 
    close(sockfd);
	//clean up the memory mapping
	close_map_base();
    exit(-1);
}

int main(int argc, char *argv[])
{
     int portno;
     int pid;  // forked child process id
	 unsigned int data_length;
	 unsigned long address;
     socklen_t clilen;

     char data_buffer[8+sizeof(unsigned long)*MAX_LENGTH];
	 unsigned long * rw_buffer =(unsigned long*)&(data_buffer[8]);
	 char* buffer = (char*)&(data_buffer[0]);
     char* token;

     // get command line arguments
     if (argc < 2) {
         fprintf(stderr,"ERROR, no port provided\n");
         exit(1);
     }
     portno = atoi(argv[1]);
     if (argc < 3) {
         fprintf(stderr,"ERROR, no token provided\n");
         exit(1);
     }
     token = argv[2];
     if (strlen(token) != 32) {
         fprintf(stderr,"ERROR, token (%s) must be 32 characters long\n", token);
         exit(1);
     }

     struct sockaddr_in serv_addr, cli_addr;
     int n;
     sockfd = socket(AF_INET, SOCK_STREAM, 0);
     if (sockfd < 0) 
         error("ERROR opening socket");
	 int enable = 1;
	 if (setsockopt(sockfd,SOL_SOCKET,SO_REUSEADDR,&enable,sizeof(int))<0)
		 error("setsockopt(SO_REUSEADDR) failed");
     bzero((char *) &serv_addr, sizeof(serv_addr));
     serv_addr.sin_family = AF_INET;
     serv_addr.sin_addr.s_addr = INADDR_ANY;
     serv_addr.sin_port = htons(portno);
     if (bind(sockfd, (struct sockaddr *) &serv_addr,
              sizeof(serv_addr)) < 0) 
              error("ERROR on binding");
     listen(sockfd,5);
     clilen = sizeof(cli_addr);

     //server service loop
     for (;;)
     {
         newsockfd = accept(sockfd,
                     (struct sockaddr *) &cli_addr,
                     &clilen);

         if ((pid = fork()) == -1)  // fork failed, go to accept new connections
         {
             close(newsockfd);
             printf("fork() failed, waiting for new connections...");
             continue;
         }
         else if(pid > 0)  // parent process, close new socket and go back to accept new connections
         {
             close(newsockfd);
             printf("Forked successfully!");
             continue;
         }
         else if(pid == 0)
         {
             if (newsockfd < 0)
                  error("ERROR on accept");
             else
                  printf("Incoming client connection accepted!");
             //authentification procedure
             bzero(buffer,33);
             n = recv(newsockfd,buffer,32,MSG_WAITALL);
             if (n < 0) error("ERROR reading from socket");
             if (n != 32) error("ERROR reading from socket - incorrect token length");
             if (strcmp(buffer,token) != 0)
             {
                 // wrong token, but tell the client what the correct token would have looked like
                 n = send(newsockfd,(void*)token,32,0);
                 if (n < 0) error("ERROR writing to socket");
                 if (n != 32) error("ERROR wrote incorrect number of bytes to socket");
                 error("Authentification failure - wrong token. Terminating client!");
             }
             //confirm connection by sending a constant token back to the client
             n = send(newsockfd,(void*)("11111111111111111111111111111111"),32,0);
             if (n < 0) error("ERROR writing to socket");
             if (n != 32) error("ERROR wrote incorrect number of bytes to socket");

             for(;;)
             {   //service loop
                 //read next header from client
                 bzero(buffer,8);
                 n = recv(newsockfd,buffer,8,MSG_WAITALL);
                 if (n < 0) error("ERROR reading from socket");
                 if (n != 8) error("ERROR reading from socket - incorrect header length");
                 //confirm control sequence
                 ////n=send(newsockfd,buffer,8,0);
                 ////if (n != 8) error("ERROR control sequence mirror incorreclty transmitted");
                 //interpret the header
                 address = ((unsigned long*)buffer)[1]; //address to be read/written
                 data_length = buffer[2]+(buffer[3]<<8); //number of "unsigned long" to be read/written
                 if (data_length > MAX_LENGTH)
                     data_length = MAX_LENGTH;
                 if (data_length == 0)
                    continue;
                 //test for various cases Read, Write, Close
                 else if (buffer[0] == 'r') { //read from FPGA
                    read_values(address, rw_buffer, data_length);
                    //send the data
                    n = send(newsockfd,(void*)data_buffer,data_length*sizeof(unsigned long)+8,0);
                    if (n < 0) error("ERROR writing to socket");
                    if (n != data_length*sizeof(unsigned long)+8) error("ERROR wrote incorrect number of bytes to socket");
                 }
                 else if  (buffer[0] == 'w') { //write to FPGA
                    //read new data from socket
                    n = recv(newsockfd,(void*)rw_buffer,data_length*sizeof(unsigned long),MSG_WAITALL);
                    if (n < 0) error("ERROR reading from socket");
                    if (n != data_length*sizeof(unsigned long)) error("ERROR read incorrect number of bytes to socket");
                    //write FPGA memory
                    write_values(address, rw_buffer, data_length);
                    n=send(newsockfd,buffer,8,0);
                    if (n != 8) error("ERROR control sequence mirror incorrectly transmitted");
                 }
                 else if (buffer[0] == 'c') break; //close program
                 else error("ERROR unknown control character - server and client out of sync"); //if an unknown control sequence is received, terminate for security reasons
             }
             //close the socket
             close(newsockfd);
             close(sockfd);
             //clean up the memory mapping
             close_map_base();
             return 0;
         }
     }
}


// old version with steady reinstantiation of mmap (slow)
unsigned long* read_values(unsigned long a_addr, unsigned long* a_values_buffer, unsigned long a_len) {
    int fd = -1;
    if((fd = open("/dev/mem", O_RDWR | O_SYNC)) == -1) FATAL;
    map_base = mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, a_addr & ~MAP_MASK);
	if(map_base == (void *) -1) FATAL;
	
	void* virt_addr = map_base + (a_addr & MAP_MASK);
	unsigned long i;
	for (i = 0; i < a_len; i++) {
		a_values_buffer[i] = ((unsigned long*) virt_addr)[i];
	}

	if (map_base != (void*)(-1)) {
		if(munmap(map_base, MAP_SIZE) == -1) FATAL;
		map_base = (void*)(-1);
	}
	if (fd != -1) {
		close(fd);
	}
	return a_values_buffer;
}

void write_values(unsigned long a_addr, unsigned long* a_values, unsigned long a_len) {
    int fd = -1;
    if((fd = open("/dev/mem", O_RDWR | O_SYNC)) == -1) FATAL;
    map_base = mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, a_addr & ~MAP_MASK);
	if(map_base == (void *) -1) FATAL;
	
	void* virt_addr = map_base + (a_addr & MAP_MASK);
	unsigned long i;
	for (i = 0; i < a_len; i++) {
				((unsigned long *) virt_addr)[i] = a_values[i];
	}
	
	if (map_base != (void*)(-1)) {
		if(munmap(map_base, MAP_SIZE) == -1) FATAL;
		map_base = (void*)(-1);
	}
	if (fd != -1) {
		close(fd);
	}
}
