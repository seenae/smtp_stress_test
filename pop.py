import poplib
import email


def check_pop_receive(pop_server, email_id, pwd, subject, ssl=True):
    conn = None
    try:
        if ssl:
            conn = poplib.POP3_SSL(pop_server)
        else:
            conn = poplib.POP3(pop_server)
        conn.user(email_id)
        conn.pass_(pwd)

        numMessages = conn.stat()[0]
        raw_email = '\n'.join(conn.retr(numMessages)[1])
        msg = email.message_from_string(raw_email)
        if msg['subject'] == subject:
            return 'PASS'
    except:
        return 'FAIL'
    finally:
        if conn:
            conn.quit()
    return 'FAIL'
