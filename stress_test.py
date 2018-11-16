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
#logging.basicConfig(level=logging.DEBUG)
from ratelimit import limits
from multiprocessing import Process
from ratelimiter import RateLimiter
from tabulate import tabulate
from ratelimit import limits
import threading 
from opentsdb import TSDBClient

PRESERVE_SESSION = True
tsdb = TSDBClient('internal-hugemetric-1216732828.us-east-1.elb.amazonaws.com', static_tags={'node': 'OutBoundTestNode'})
MAX_MAILS = 10
MAX_RATE = 2
SMTP_LOGIN_TIME = []
SMTP_SENDMAIL_TIME = []
MAX_CONCURRENT_CONNECTIONS = 200
CONCURRENT_SMTPs = []
FAILED_MAILS = []
SMTP_HOST = 'smtp.flockmail.com'
CALL_COUNTER = []
TEST_CLUSTER = 'Outbound'
TIME_PERIOD = 1
LOCAL = False
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

@RateLimiter(max_calls=MAX_RATE, period=TIME_PERIOD)
def perform_smtp_test(sender, receiver, auth=True, smtp_host=SMTP_HOST, files=None, receive_method='imap'):
    subject = uuid.uuid4().hex
    CALL_COUNTER.append("done")

    pwd = sender['pwd'] if auth else None
    send_status, login_time_taken, mail_time_taken = send_mail(smtp_host, sender['email_id'], pwd,
                            [receiver['email_id']], subject, '', files=files)

    if send_status == 'FAIL':
        FAILED_MAILS.append('failed')
        print(len(FAILED_MAILS))
        return 'FAIL', 'FAIL'

    if login_time_taken > 0:
        SMTP_LOGIN_TIME.append(login_time_taken)
    if mail_time_taken > 0:
        SMTP_SENDMAIL_TIME.append(mail_time_taken)

@RateLimiter(max_calls=MAX_RATE, period=TIME_PERIOD)
def perform_smtp_test_preserved(sender, receiver, smtp_conn, auth=True, smtp_host=SMTP_HOST, files=None, receive_method='imap'):
    subject = uuid.uuid4().hex
    CALL_COUNTER.append("done")

    pwd = sender['pwd'] if auth else None
    send_status, login_time_taken, mail_time_taken = preserve_connection_send(smtp_host, sender['email_id'], pwd,
                            [receiver['email_id']], subject, '', smtp_conn, files=files)
    
    if send_status == 'FAIL':
        FAILED_MAILS.append('failed')
        print("failed")
        return 'FAIL', 'FAIL'

    if login_time_taken > 0:
        SMTP_LOGIN_TIME.append(login_time_taken)
    if mail_time_taken > 0:
        SMTP_SENDMAIL_TIME.append(mail_time_taken)

def stress_test_smtp(smtp_host=SMTP_HOST, ssl_percentage=0, preserve=PRESERVE_SESSION):
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
            start = time.time()
            conn.login(CREDS['fmail2']['email_id'], CREDS['fmail2']['pwd'])
            login_time = time.time() - start
        else:
            login_time = -1
        if login_time > 0:
            SMTP_LOGIN_TIME.append(login_time)         
    for i in range(0, MAX_MAILS):
        if preserve:
            perform_smtp_test_preserved(CREDS['fmail2'], CREDS['fmail1'],conn)
        else:
            perform_smtp_test(CREDS['fmail2'], CREDS['fmail1'])
    conn.quit()             
      #  perform_smtp_test_preserved_connect(CREDS['fmail2'], CREDS['fmail1'],CONCURRENT_SMTPs[i%MAX_CONCURRENT_CONNECTIONS])

def count():
    prev_login_count = 0
    prev_mail_count = 0
    count = 0
    prev = 0
    while len(CALL_COUNTER) < MAX_CONCURRENT_CONNECTIONS*MAX_MAILS:
        count = count + 1
        if len(SMTP_SENDMAIL_TIME) > 0:
            i = len(SMTP_SENDMAIL_TIME) - 1
            if len(SMTP_SENDMAIL_TIME)-prev_mail_count > 0:
                if count == 10:
                    mail_data_array = SMTP_SENDMAIL_TIME[prev_mail_count:len(SMTP_SENDMAIL_TIME)]
                    tsdb.send('stress_test.mail_time_taken_95p', np.percentile(mail_data_array,95), tag1=TEST_CLUSTER)
                    tsdb.send('stress_test.mail_time_taken_90p', np.percentile(mail_data_array,90), tag1=TEST_CLUSTER)
                    tsdb.send('stress_test.mail_time_taken_avg', np.average(mail_data_array), tag1=TEST_CLUSTER)
                    count = 0
                tsdb.send('stress_test.mail_count', len(SMTP_SENDMAIL_TIME)-prev_mail_count, tag1=TEST_CLUSTER)
                for k in range(prev,i):
                    tsdb.send('stress_test.mail_time_taken_in_seconds', SMTP_SENDMAIL_TIME[k], tag1=TEST_CLUSTER)
                prev = i    
                tsdb.send('stress_test.login_count', len(SMTP_LOGIN_TIME)-prev_login_count, tag1=TEST_CLUSTER)
                tsdb.send('stress_test.login_time_taken_in_seconds', SMTP_LOGIN_TIME[i], tag1=TEST_CLUSTER)
            prev_login_count = len(SMTP_LOGIN_TIME)
            prev_mail_count = len(SMTP_SENDMAIL_TIME)
        time.sleep(1)

def report():
    test_start_time = time.time()
    thread_list = []
    for i in range(0,MAX_CONCURRENT_CONNECTIONS):
        thread = threading.Thread(target=stress_test_smtp, args=())
        thread_list.append(thread)
    tt = threading.Thread(target=count, args=())
    tt.start()      
    for thread in thread_list:
        thread.start()  
    for thread in thread_list:
        thread.join()
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

report()    


