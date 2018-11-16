import imaplib
import email


def check_imap_receive(imap_server, email_id, pwd, subject, ssl=True):
    conn = None
    try:
        if ssl:
            conn = imaplib.IMAP4_SSL(imap_server)
        else:
            conn = imaplib.IMAP4(imap_server)

        conn.login(email_id, pwd)
        retcode, resp = conn.select(readonly=True)
        num = resp[0].decode('utf-8')
        if retcode != 'OK':
            return 'FAIL'
        
        ret, msg_data = conn.fetch(num, '(RFC822)')
        if ret == 'OK' and msg_data:
            msg = email.message_from_string(msg_data[0][1])
            if msg['subject'] == subject:
                return 'PASS'
    except:
        return 'FAIL'
    finally:
        if conn:
            conn.close()
            conn.logout()

    return 'FAIL'
