from pop import check_pop_receive
from imap import check_imap_receive
from smtp import send_mail, send_mail_attachments, preserve_connection_send
import os
import sys
import time
import uuid
import tempfile
import random
import numpy as np
import smtplib
import logging
import sys, getopt
logging.basicConfig(level=logging.DEBUG)
from ratelimit import limits
from multiprocessing import Process
from ratelimiter import RateLimiter
from tabulate import tabulate
from ratelimit import limits
import threading 
from opentsdb import TSDBClient

tsdb = TSDBClient('internal-hugemetric-1216732828.us-east-1.elb.amazonaws.com', static_tags={'node': 'OutBoundTestNode'})

MAILS_PER_THREAD = 5
MAX_RATE = 1
MAX_THREADS = 1
SMTP_HOST = 'smtp.flockmail.com'
TEST_CLUSTER = 'Outbound'
TIME_PERIOD = 1
LOCAL = False
PRESERVE_SESSIONS = False


#global lists
CONCURRENT_SMTPs = []
SMTP_SENDMAIL_TIME = []
SMTP_LOGIN_TIME = []
FAILED_MAILS = []
CALL_COUNTER = []

CREDS = {
    'fmail1': {
        'email_id': 'test1@flockmail.com',
        'pwd': 'test1pass@123'
    },
    'fmail2': {
        'email_id': 'test2@flockmail.com',
        'pwd': 'test2pass@123'
    },
    'gmail': {
        'email_id': 'flockdevops@gmail.com',
        'pwd': 'sMndhEh&ydra!!yathi'
    },
    'incorrect_domain': {
        'email_id': 'random@flock123.com'
    }
}

Out_delivery_mail_addr = {'email_id':'krishna@email-test.ops.flock.com'}

def main(argv):
    global MAX_RATE
    global MAX_THREADS
    global MAILS_PER_THREAD
    global PRESERVE_SESSIONS
    global SMTP_HOST
    global TIME_PERIOD
    global TEST_CLUSTER
    try:
      opts, args = getopt.getopt(argv,"h:r:m:t:p:",["max_rate=","max_mails=","max_threads=","preserve=","smtp_host=","test_cluster=","time_period=",])
    except getopt.GetoptError:
      print('Usage: stress_test.py -r <rate> -m <max_mails> -t <max_threads> -p <preserve_connections> \n \
                            where :  \n \
                                  -r or --max_rate = maximum rate at which mails will be send to the server\n \
                                  -m or --max_mails = maximum number of mails which will be send\n \
                                  -t or --max_threads = maximum number of threads which will be created \n \
                                                        Note: if preserve=True this number will be max number of concurrent connections to the server.\n \
                                  -p or --preserve = whether to preserve the smtp session connection object for next mails: Value= True or False\n \
                                  -host or --smtp_host = SMTP HOST TO BE TESTED\n \
                                  -cluster or --test_cluster = Inbound or OutBound \n \
                                  -tp or --time_period = time_period for max_rate is considered default is 1 second\n')
      sys.exit(2)
    print(opts)      
    for opt, arg in opts:
       if opt == '-h':
           print('Usage: stress_test.py -r <rate> -m <max_mails> -t <max_threads> -p <preserve_connections> \n \
                            where :  \n \
                                  -r or --max_rate = maximum rate at which mails will be send to the server\n \
                                  -m or --max_mails = maximum number of mails which will be send\n \
                                  -t or --max_threads = maximum number of threads which will be created \n \
                                                        Note: if preserve=True this number will be max number of concurrent connections to the server.\n \
                                  -p or --preserve = whether to preserve the smtp session connection object for next mails: Value= True or False\n \
                                  -host or --smtp_host = SMTP HOST TO BE TESTED\n \
                                  -cluster or --test_cluster = Inbound or OutBound \n \
                                  -tp or --time_period = time_period for max_rate is considered default is 1 second\n')
           sys.exit()
       elif opt in ("-r", "--max_rate"):
            MAX_RATE = int(arg)
       elif opt in ("-m", "--max_mails"):
            MAX_MAILS = int(arg)
       elif opt in ("-t", "--max_threads"):
            MAX_THREADS = int(arg)
       elif opt in ("-p", "--preserve"):
           if arg == 'True':
               PRESERVE_SESSIONS = True
           else:
               PRESERVE_SESSIONS = False    
       elif opt in ("--smtp_host"):
            SMTP_HOST = arg
       elif opt in ("--test_cluster"):
            TEST_CLUSTER = arg
       elif opt in ("--time_period"):
            TIME_PERIOD = int(arg)

    MAILS_PER_THREAD = int(MAX_MAILS/MAX_THREADS)
    report()
    # 
                         
def perform_smtp_test(sender, receiver, auth=True, smtp_host=SMTP_HOST, files=None, receive_method='imap'):
    subject = uuid.uuid4().hex

    pwd = sender['pwd'] if auth else None
    try:
        send_status, login_time_taken, mail_time_taken = send_mail(smtp_host, sender['email_id'], pwd,
                            [receiver['email_id']], subject, '', files=files)
    except:
        send_status = 'FAIL'
        login_time_taken = -1
        mail_time_taken = -1
    else:
        send_status = 'UNKNOWN'
        login_time_taken = -1
        mail_time_taken = -1           
    if send_status == 'FAIL':
        FAILED_MAILS.append('failed')
        #print(len(FAILED_MAILS))

    if login_time_taken > 0:
        SMTP_LOGIN_TIME.append(login_time_taken)
    if mail_time_taken > 0:
        SMTP_SENDMAIL_TIME.append(mail_time_taken)
    CALL_COUNTER.append("done")    

# @RateLimiter(max_calls=MAX_RATE, period=TIME_PERIOD)
def perform_smtp_test_preserved(sender, receiver, smtp_conn, auth=True, smtp_host=SMTP_HOST, files=None, receive_method='imap'):
    subject = uuid.uuid4().hex

    pwd = sender['pwd'] if auth else None
    try:
        send_status, login_time_taken, mail_time_taken = preserve_connection_send(smtp_host, sender['email_id'], pwd,
                                [receiver['email_id']], subject, '', smtp_conn, files=files)
    except:
        pass     
    if send_status == 'FAIL':
        FAILED_MAILS.append('failed')
        #print("failed")
        return 'FAIL', 'FAIL'

    if login_time_taken > 0:
        SMTP_LOGIN_TIME.append(login_time_taken)
    if mail_time_taken > 0:
        SMTP_SENDMAIL_TIME.append(mail_time_taken)
    CALL_COUNTER.append("done")    

def stress_test_smtp(smtp_host=SMTP_HOST, ssl_percentage=0, preserve=PRESERVE_SESSIONS):
    # print('p',PRESERVE_SESSIONS)
    # print('pres',preserve)
    if preserve:
        if LOCAL:
            pwd = False
            ssl = False
        else:
            pwd = True
            ssl = True   
        if ssl:
            conn = smtplib.SMTP_SSL(smtp_host)
        else:
            conn = smtplib.SMTP(smtp_host)
        if pwd:
            try:
                start = time.time()
                conn.login(CREDS['fmail2']['email_id'], CREDS['fmail2']['pwd'])
                login_time = time.time() - start
            except:
                return    
        else:
            login_time = -1
        if login_time > 0:
            SMTP_LOGIN_TIME.append(login_time)
            tsdb.send('stress_test.login_count_total', len(SMTP_LOGIN_TIME), cluster=TEST_CLUSTER)
    ratelimiter = RateLimiter(max_calls=MAX_RATE, period=TIME_PERIOD)
    # print('mr',MAX_RATE)  
    # print('mpt',MAILS_PER_THREAD)               
    for i in range(0, MAILS_PER_THREAD):
        with ratelimiter:
            if preserve:
                perform_smtp_test_preserved(CREDS['fmail2'], Out_delivery_mail_addr ,conn)
            else:
                perform_smtp_test(CREDS['fmail2'], Out_delivery_mail_addr)
    if preserve:
        conn.quit()             
      #  perform_smtp_test_preserved_connect(CREDS['fmail2'], CREDS['fmail1'],CONCURRENT_SMTPs[i%MAX_THREADS])

def count():
    prev_login_count = 0
    prev_mail_count = 0
    count = 0
    prev = 0
    while len(CALL_COUNTER) < MAX_THREADS*MAILS_PER_THREAD:
        count = count + 1
        if len(SMTP_SENDMAIL_TIME) > 0:
            i = len(SMTP_SENDMAIL_TIME) - 1
            if len(SMTP_SENDMAIL_TIME)-prev_mail_count > 0:
                if count == 10:
                    mail_data_array = SMTP_SENDMAIL_TIME[prev_mail_count:len(SMTP_SENDMAIL_TIME)]
                    tsdb.send('stress_test.mail_time_taken_95p', np.percentile(mail_data_array,95), cluster=TEST_CLUSTER)
                    tsdb.send('stress_test.mail_time_taken_90p', np.percentile(mail_data_array,90), cluster=TEST_CLUSTER)
                    tsdb.send('stress_test.mail_time_taken_avg', np.average(mail_data_array), cluster=TEST_CLUSTER)
                    count = 0
                tsdb.send('stress_test.mail_count', len(SMTP_SENDMAIL_TIME)-prev_mail_count, cluster=TEST_CLUSTER)
                for k in range(prev,i):
                    tsdb.send('stress_test.mail_time_taken_in_seconds', SMTP_SENDMAIL_TIME[k], cluster=TEST_CLUSTER)
                prev = i
                prev_mail_count = len(SMTP_SENDMAIL_TIME)        
        if len(SMTP_LOGIN_TIME)-prev_login_count > 0:
            tsdb.send('stress_test.login_count', len(SMTP_LOGIN_TIME)-prev_login_count, cluster=TEST_CLUSTER)
            tsdb.send('stress_test.login_time_taken_in_seconds', SMTP_LOGIN_TIME[len(SMTP_SENDMAIL_TIME)-1], cluster=TEST_CLUSTER)
            tsdb.send('stress_test.login_count_total', len(SMTP_LOGIN_TIME), cluster=TEST_CLUSTER)    
            prev_login_count = len(SMTP_LOGIN_TIME)
        tsdb.send('stress_test.failed_mails_count', len(FAILED_MAILS), cluster=TEST_CLUSTER)    
        time.sleep(1)

def report():
    test_start_time = time.time()
    thread_list = []
    # print('mt',MAX_THREADS)
    for i in range(0,MAX_THREADS):
        thread = threading.Thread(target=stress_test_smtp, args=())
        thread_list.append(thread)
    tt = threading.Thread(target=count, args=())
    tt.start()      
    for thread in thread_list:
        thread.start()  
    for thread in thread_list:
        thread.join()
    print(len(CALL_COUNTER))    
    tt.join()
    total_time_taken = time.time() - test_start_time            
    #stress_test_smtp_concurrent(smtp_host=SMTP_HOST)
    login_stats = []
    mail_stats = []
    data_array_login_time = np.array(SMTP_LOGIN_TIME)
    data_array_mail_time = np.array(SMTP_SENDMAIL_TIME)
    # Login data stats
    login_stats.append("LOGIN STATS")
    login_stats.append(len(data_array_login_time))
    login_stats.append(np.average(data_array_login_time))
    login_stats.append(np.percentile(data_array_login_time,50))
    login_stats.append(np.percentile(data_array_login_time,80))
    login_stats.append(np.percentile(data_array_login_time,90))
    login_stats.append(np.percentile(data_array_login_time,95))
    login_stats.append(np.percentile(data_array_login_time,99))
    mail_stats.append("Mail Stats")
    mail_stats.append(len(data_array_mail_time))
    mail_stats.append(np.average(data_array_mail_time))
    mail_stats.append(np.percentile(data_array_mail_time,50))
    mail_stats.append(np.percentile(data_array_mail_time,80))
    mail_stats.append(np.percentile(data_array_mail_time,90))
    mail_stats.append(np.percentile(data_array_mail_time,95))
    mail_stats.append(np.percentile(data_array_mail_time,99))
    headers=['S','Total No of Mails','Avg','50th %','80th %','90th %','95th %','99th %']
    print("\n\n")
    print(tabulate([login_stats,mail_stats],headers))
    print("\n\n")
    print(tabulate([[len(FAILED_MAILS),len(CALL_COUNTER),total_time_taken]],['FAILED MAILS','TOTAL MAILS','TOTAL_TIME_TAKEN']))

   
if __name__ == "__main__":
   main(sys.argv[1:])
   print("\n\n",MAX_RATE,MAX_THREADS,MAILS_PER_THREAD,TIME_PERIOD,PRESERVE_SESSIONS)    


