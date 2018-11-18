import smtplib
from os.path import basename
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from essential_generators import DocumentGenerator
from email.utils import formatdate
import time
import os
import random
import socket

gen = DocumentGenerator()

def send_mail(smtp_host, sender, pwd, recepients, subject, text, files=None, ssl=True):
    fail = False
    try:
        msg = MIMEMultipart()
        msg['Subject'] = gen.sentence().split(".")[0]
        msg['From'] = sender
        msg['To'] = ', '.join(recepients)
        body = gen.paragraph()
        msg["Date"] = formatdate(localtime=True)
        msg.attach(MIMEText(body, 'plain'))
        text = gen.url()
        msg.attach(MIMEText(text))

        for file_name in files or []:
            with open(file_name, "rb") as fp:
                part = MIMEApplication(
                    fp.read(),
                    Name=basename(file_name)
                )
            part['Content-Disposition'] = 'attachment; filename="{}"'.format(
                basename(file_name))
            msg.attach(part)
        # print(smtp_host)
        # pwd = False
        # ssl = False
        if ssl:
            socket.setdefaulttimeout(2 * 60)
            server = smtplib.SMTP_SSL(host=smtp_host, port=0, local_hostname=None, timeout=2*60)
        else:
            socket.setdefaulttimeout(2 * 60)
            server = smtplib.SMTP(host=smtp_host, port=0, local_hostname=None, timeout=2*60)
        server.set_debuglevel(True)
        
        if pwd:
            start = time.time()
            server.login(sender, pwd)
            login_time = time.time() - start
        else:
            login_time = -1    
        start = time.time()    
        server.sendmail(sender, recepients, msg.as_string())
        sendmail_time = time.time() - start
    except Exception as e:
        print(e)
        fail = True
        return ('FAIL',-1,-1)
    finally:
        if not 'server' in locals():
            fail = True
        if server:
            server.quit()
        # print(login_time,sendmail_time)
    if fail:
        return ('FAIL',-1,-1)   
    return ('PASS',login_time,sendmail_time)

def send_mail_attachments(smtp_host, sender, pwd, recepients, subject, text, files=None, ssl=True):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = gen.sentence().split(".")[0]
        msg['From'] = sender
        msg['To'] = ', '.join(recepients)
        body = gen.paragraph()
        msg["Date"] = formatdate(localtime=True)
        msg.attach(MIMEText(body, 'plain'))
        text = gen.url()
        msg.attach(MIMEText(text))

        files_list = os.listdir("/home/kk/009/")

        file_no = random.randint(0,999)%990
        
        files = ["/home/kk/009/"+files_list[file_no]]
        print(files)
        for file_name in files or []:
            with open(file_name, "rb") as fp:
                part = MIMEApplication(
                    fp.read(),
                    Name=basename(file_name)
                )
            part['Content-Disposition'] = 'attachment; filename="{}"'.format(
                basename(file_name))
            msg.attach(part)

        if ssl:
            server = smtplib.SMTP_SSL(smtp_host)
        else:
            server = smtplib.SMTP(smtp_host)

        if pwd:
            start = time.time()
            server.login(sender, pwd)
            login_time = time.time() - start
        else:
            login_time = -1    
        start = time.time()    
        server.sendmail(sender, recepients, msg.as_string())
        sendmail_time = time.time() - start
    except:
        return 'FAIL',-1,-1
    finally:
        if server:
            server.quit()
    return ('PASS',login_time,sendmail_time)

def preserve_connection_send(smtp_host, sender, pwd, recepients, subject, text, smtp_conn, files=None, ssl=True,attachment=None):
    server = smtp_conn
    try:
        msg = MIMEMultipart()
        msg['Subject'] = gen.sentence().split(".")[0]
        msg['From'] = sender
        msg['To'] = ', '.join(recepients)
        body = gen.paragraph()
        msg["Date"] = formatdate(localtime=True)
        msg.attach(MIMEText(body, 'plain'))
        text = gen.url()
        msg.attach(MIMEText(text))
        if(attachment):
            files_list = os.listdir("/home/kk/009/")

            file_no = random.randint(0,999)%990
            
            files = ["/home/kk/009/"+files_list[file_no]]
            for file_name in files or []:
                with open(file_name, "rb") as fp:
                    part = MIMEApplication(
                        fp.read(),
                        Name=basename(file_name)
                    )
                part['Content-Disposition'] = 'attachment; filename="{}"'.format(
                    basename(file_name))
                msg.attach(part)
                
        
        login_time = -1    
        start = time.time()    
        server.sendmail(sender, recepients, msg.as_string())
        sendmail_time = time.time() - start
    except:
        return 'FAIL',-1,-1
    return ('PASS',login_time,sendmail_time)

