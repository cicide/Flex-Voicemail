#this class handles the leaving of voicemail
class VmDeposit:

    def __init__(self):
        self.count = 0

    def __call__(self, agi, cidname, cidnum, gid, exten, cuid):
        self.gid = gid
        self.agi = agi
        self.exten = exten
        self.cuid = cuid
        self.cidname = cidname
        self.cidnum = cidnum
        self.email_attach_flag = 0
        self.vm_enable = group.groups[self.gid].getVmEmail(self.exten)
        if self.vm_enable in (0,1):
            self.email_attach_flag = 0
        else:
            self.email_attach_flag = 1
        return self.start()

    def onFailure(self, error):
        #must include hangup otherwise the dialplan will keep recycling into voicemail
        log.debug("Got failure event in voicemail deposit: %s" % error)
        sequence = fastagi.InSequence()
        sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence().addErrback(onFailure)

    def onErrComplete(self, result=None):
        #must include hangup otherwise the dialplan will keep recycling into voicemail
        sequence = fastagi.InSequence()
        sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence().addErrback(self.onFailure)

    def start(self):
        def onFailure(reason):
            log.error("AGI Failure: %s" % reason.getTraceback())
            agi.finish()
        def onResponse(result):
            log.debug("response result: %s" % result)
        log.debug("starting voicemail deposit")
        call.calls[self.cuid].logEvent('vmDeposit')
        call.calls[self.cuid].setCurrentStatus('vmDeposit')
        #increment usage count
        self.count += 1
        self.tries = 0
        log.debug("-*-*-*- Answered Call in VmDeposit module with agi %s" % self.agi)
        return self.agi.answer().addCallback(self.onAnswered)

    def onAnswered(self, result=None):
        return self.agi.wait(1.0).addCallbacks(self.onWaited,self.onFailure)

    def onWaited(self, result=None):
        if not self.vm_enable:
            msg_list = []
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_not_avail'})
            r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 0, 0)
            return r.addCallbacks(self.onErrComplete,self.onFailure)
        else:
            ext_msg = '%s/%s/%s/vm_greet' % (vm_files_dir, self.gid, self.exten)
            try:
                fileloc = '%s.sln' % ext_msg
                tmp = os.stat(file_loc)
                msg_list = []
                msg_list.append({'prompt_type': 'location', 'prompt_val': '%s' % ext_msg})
                r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
                return r.addCallbacks(self.onGreetingPlayed,self.onFailure)
            except:
                msg_list = []
                msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_default_greeting'})
                r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
                return r.addCallbacks(self.onGreetingPlayed,self.onFailure)

    def onGreetingPlayed(self, result=None):
        #insert a db record and get the key
        self.create_time = int(time.time())
        d = txdb.addVmRecord(self.gid, self.exten, self.cidname.strip(), self.cidnum.strip(), self.create_time, 0, 0, '', 0, 0)
        d.addCallbacks(self.onInsertId,self.onFailure)

    def onInsertId(self, result):
        log.debug("got result from db: %s" % result)
        self.msg_id = result
        #we will either have a positive integer here, or we will have a none, if we get an integer, we can
        #proceed to recording the voicemail
        if result:
            self.file_loc = '%s/%s/%s/vm%s' % (vm_files_dir, self.gid, self.exten, result)
            log.debug("recording voicemail to: %s" % self.file_loc)
            return self.agi.recordFile(self.file_loc, 'wav', '#0', 300).addCallback(self.onMessageRecorded).addErrback(self.onMessageRecordedErr)

    def onMessageRecordedErr(self, reason):
        #we probably got here due to a hangup, save the message and issue a hangup
        self.end_time = int(time.time())
        self.agi.finish()
        return self.onMessageSaved()

    def onMessageRecorded(self, result=None):
        msg_list =[]
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_was_recorded'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0, 0)
        #This is not the correct way to play this recoreded message - FIX
        log.debug("in vm Deposit onMessageRecorded for %s" % self.gid)
        code = result[0]
        typeOfExit = result[1]
        endpos = result[2]
        self.end_time = int(time.time())
        log.debug("recording terminated with result: %s" % typeOfExit)
        if typeOfExit == 'timeout':
            #message length exceeded, save message
            sequence = fastagi.InSequence()
            sequence.append(self.agi.wait,1)
            sequence.append(self.agi.playback, r)
            sequence.append(self.agi.hangup)
            sequence.append(self.agi.finish)
            return sequence().addCallback(self.onMessageSaved)
        elif typeOfExit == 'hangup':
            #should we trash the message or save it, and send it?
            sequence = fastagi.InSequence()
            sequence.append(self.agi.hangup)
            sequence.append(self.agi.finish)
            return sequence().addCallback(self.onMessageSaved)
        elif typeOfExit == 'dtmf':
            #user completed recordind and pressed the escape dtmf
            sequence = fastagi.InSequence()
            sequence.append(self.agi.wait,1)
            sequence.append(self.agi.playback, r)
            sequence.append(self.agi.hangup)
            sequence.append(self.agi.finish)
            return sequence().addCallback(self.onMessageSaved)
        else:
            #no idea how we got here, toss an error and report the result value
            log.debug("invalid exit received from vm deposit message recording: %s" % result)
            sequence = fastagi.InSequence()
            sequence.append(self.agi.wait, 1)
            sequence.append(self.agi.playback,r)
            sequence.append(self.agi.hangup)
            sequence.append(self.agi.finish)
            return sequence().addCallback(self.onMessageSaved)

    def onMessageSaved(self, result=None):
        self.vm_dur = self.end_time - self.create_time
        self.vm_utc_day =  datetime.datetime.utcfromtimestamp(self.create_time).strftime("%B %d")
        self.vm_utc_time = datetime.datetime.utcfromtimestamp(self.create_time).strftime("%I:%M %p")
        if self.vm_dur < 3:
            #caller left a blank message
            self.vm_status = -1
        else:
            self.vm_status = 0
        sql = """UPDATE voicemail SET duration=%i, status=%i, file='%s' WHERE id = %i""" % (self.vm_dur, self.vm_status, self.file_loc, self.msg_id)
        d = aexecute(sql)
        d.addErrback(self.onFailure)
        log.debug("Checking whether to send an email for this voicemail: %s" % self.vm_enable)
        if self.vm_enable == 0:
            pass
        else:
            self.sendVmailEmail(int(self.vm_enable))
        
    def sendVmailEmail(self, result=None):
        def encodeMessage(message, outer, email_to, email_from):
            outer.attach(message)
            return message.as_string().addCallback(sendEmail, email_to, email_from)
        def sendEmail(message, email_from, email_to):
            s = smtplib.SMTP(smtp_server)
            s.sendmail(email_from, email_to, message)
            return s.quit()
        def composeMessage(email_from, email_to):
            if self.email_attach_flag:
                log.debug("getting mimetype for file: %s.wav" %self.file_loc)
                ctype, encoding = mimetypes.guess_type('%s.wav' % self.file_loc)
                log.debug("ctype: %s" % ctype)
                maintype, subtype = ctype.split('/', 1)
                file_loc = '%s.wav' % self.file_loc
                fp = open(file_loc, 'rb')
                msg = MIMEAudio(fp.read(), _subtype=subtype)
                fp.close()
                msg.add_header('Content-Disposition', 'attachment', filename = 'voicemail.wav')
                outer.attach(msg)
            composed = outer.as_string()
            s = smtplib.SMTP(smtp_server)
            x = s.sendmail(email_from, email_to, composed)
            x = s.quit()
            log.debug("Email sent")
        log.debug("sendVmailEmail reports result: %s" % result)
        if not self.vm_enable:
            pass
        else:
            from email import encoders
            from email.message import Message
            from email.mime.audio import MIMEAudio
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            outer = MIMEMultipart()
            outer['Subject'] = "Voicemail from %s" % self.cidname
            mail_to = group.groups[self.gid].getEmailAddress(self.exten)
            outer['To'] = email_to = mail_to
            outer['From'] = email_from = '"Callster" <noreply@callster.net>'
            #create time needs to be fixed to match the recipients time zone - FIX
            text_part = "You have received a %s second long voicemail from %s left on %s at %s UTC" % (self.vm_dur, self.cidname, self.vm_utc_day, self.vm_utc_time)
            part = MIMEText(text_part, 'plain')
            outer.attach(part)
            #convert the voicemail file to mp3 here
            reactor.callInThread(composeMessage, email_from, email_to)

#This class handles the retrieval of voicemail, as well as deleting, saving, and changing of vm pin
class VmRetrieve:

    def __init__(self):
        self.count = 0

    def __call__(self, agi, gid, exten, cuid):
        self.group = group.groups[gid]
        self.agi = agi
        self.gid = gid
        self.exten = exten
        self.cuid = cuid
        self.attempts = 0
        #self.dtmf_ack = msg_ack
        #self.file_loc = file_loc
        return self.start()

    def onFailure(self, error):
        log.debug("Got failure event in vm retrieve: %s" % error)
        sequence = fastagi.InSequence()
        #sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence().addErrback(onFailure)

    def onErrComplete(self, result=None):
        sequence = fastagi.InSequence()
        #sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence().addErrback(self.onFailure)

    def start(self):
        def onFailure(reason):
            log.error("AGI Failure: %s" % reason.getTraceback())
            agi.finish()
        def onResponse(result):
            log.debug("response result: %s" % result)
        def onMsgListSuccess(result):
            log.debug("vm message list returned %s records" % len(result))
            self.msg_count = len(result)
            self.vm_msg_list = result
            log.debug("-*-*-*- Answered Call in VmRetieve module")
            return self.agi.answer().addCallback(self.onAnswered).addErrback(onFailure)
        def onMsgListFail(reason):
            log.debug("vm message list query failed: %s" % reason)
            self.vm_msg_list = None
            log.debug("-*-*-*- Answered Call in VmRetrieve module")
            return self.agi.answer().addCallback(self.onAnswered).addErrback(onFailure)
        log.debug("starting voicemail retrieval")
        call.calls[self.cuid].logEvent('vmRetrieve')
        call.calls[self.cuid].setCurrentStatus('vmRetrieve')
        self.auth = call.calls[self.cuid].isAuthenticated()
        #increment usage count
        self.count += 1
        self.tries = 0
        log.debug("fetching voicemail messages and counting")
        df = group.groups[self.gid].getVmMessages(self.exten)
        df.addCallbacks(onMsgListSuccess, onMsgListFail)
        log.debug("vm info requested from db")

    def onAnswered(self, result=None):
        log.debug("In VmRetrieve onAnswered")
        return self.agi.wait(1.0).addCallback(self.onWaited).addErrback(onFailure)
    
    def onWaited(self, result=None):
        log.debug('In VmRetrieve onWaited')
        if self.auth['auth']:
            return self.onAuthenticated()
        else:
            msg_list= []
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'enter_vm_pin'})
            result = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 1, 8, 1, 2)
            return result.addCallbacks(self.onPinDigits,self.onFailure)

    def onPinDigits(self, result=None):
        if result:
            #got a response, check to see if the response is valid
            if group.groups[self.gid].validatePin(self.exten, result):
                #caller entered a valid pin, authenticate caller
                if call.calls[self.cuid].makeAuthenticated(self.exten):
                    self.tries = 0
                    return self.onAuthenticated()
                else:
                    return self.onErrComplete()
            else:
                #caller entered an invalid pin, play error message and recycle if tries are less than three
                self.tries += 1
                if self.tries < 3:
                    msg_list=[]
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'incorrect_pin'})
                    result = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
                    return result.addCallback(self.onPinRetry).addErrback(self.onFailure)
                else:
                    msg_list=[]
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'hangup_too_many_failures'})
                    result = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
                    return result.addCallback(self.onErrComplete).addErrback(self.onFailure)
        else:
            #didn't get a response, try again
            self.tries += 1
            if self.tries < 3:
                return self.onPinRetry()
            else:
                msg_list=[]
                msg_list.append({'prompt_type': 'system', 'prompt_val': 'hangup_too_many_failures'})
                result = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
                return result.addCallback(self.onErrComplete).addErrback(self.onFailure)

    def onPinRetry(self, result=None):
        msg_list = []
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'enter_vm_pin'})
        result = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 1, 8, 1, 2)
        return result.addCallbacks(self.onPinDigits,self.onFailure)
        
    def onAuthenticated(self, result=None):
        log.debug("In VmRetrieve onAuthenticated")
        msg_list = []
        if self.msg_count == 0:
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_no_new'})
        elif self.msg_count == 1:
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_you_have'})
            msg_list.append({'prompt_type': 'system', 'prompt_val': '1'})
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_message'})
        else:
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_you_have'})
            msg_list.append({'prompt_type': 'system', 'prompt_val': '%s' % self.msg_count})
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_messages'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
        return r.addCallback(self.onVmEntered).addErrback(onFailure)

    def onVmEntered(self, result=None):
        log.debug("In VmRetrieve onVmEntered")
        if self.msg_count == 0:
            return self.agi.finish()
        else:
            self.cur_msg = 0
            if self.vm_msg_list:
                self.message_list = self.vm_msg_list
            else:
                self.message_list = []
            #self.message_list = group.groups[self.gid].getVmMessages(self.exten)
            return self.agi.wait(1.0).addCallback(self.onPlayMessageInfo).addErrback(onFailure)

    def onPlayMessageInfo(self, endpos=0, result=None):
        log.debug("In VmRetrieve onPlayMessageInfo for message %s" % self.cur_msg)
        import time, datetime
        vm = self.message_list[self.cur_msg]
        #print vm
        #get human understandable number for readback of message number
        vm_msg_num = self.cur_msg + 1
        vm_key =vm[0]
        self.cur_vm_key = vm_key
        vm_cidnum = vm[2]
        vm_datestamp = vm[3]
        vm_date = datetime.datetime.fromtimestamp(vm_datestamp)
        vm_length = vm[5]
        vm_status = vm [4]
        vm_file = vm[6]
        vm_days_since_vm = 0
        vm_cur_ordinal = datetime.datetime.toordinal(datetime.datetime.now())
        vm_date_ordinal = datetime.datetime.toordinal(vm_date)
        vm_age_days = vm_cur_ordinal - vm_date_ordinal
        vm_age_seconds = time.time() - vm_datestamp
        #check to see if this message was received today
        msg_list = []
        if vm_age_days > 1:
            #if we don't have ordinals for this value, we could be in trouble
            msg_age_1 = '%s' % vm_age_days
            msg_age_2 = 'vm_days_ago'
            msg_age = [msg_age_1, msg_age_2]
        elif vm_age_days == 1:
            msg_age = ['vm_yesterday']
        elif vm_age_seconds >= 3600:
            vm_age_hours = int(vm_age_seconds/3600)
            msg_age_1 = '%s' % vm_age_hours
            msg_age_2 = 'vm_hours_ago'
            msg_age = [msg_age_1, msg_age_2]
        elif vm_age_seconds < 3600:
            vm_age_minutes = int(vm_age_seconds/60)
            msg_age_1 = '%s' % vm_age_minutes
            msg_age_2 = 'vm_min_ago'
            msg_age = [msg_age_1, msg_age_2]
        else:
            #this message came from the future!.
            msg_age = ['vm_in_future']
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_message'})
        msg_list.append({'prompt_type': 'system', 'prompt_val': '%s' % vm_msg_num})
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_from'})
        for num in vm_cidnum:
            msg_list.append({'prompt_type': 'system', 'prompt_val': '%s' % num})
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_received'})
        for message in msg_age:
            msg_list.append({'prompt_type': 'system', 'prompt_val': message})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 1, 1, 1, 1)
        return r.addCallback(self.onInstructResult, endpos).addErrback(self.onFailure)

    def onInstructResult(self, result=None, endpos=0):
        if not endpos:
            endpos = 0
        log.debug("In VmRetrieve onInstructResult for message %s" % self.cur_msg)
        log.debug("checking keyed result from message header for message %s" % self.cur_msg)
        log.debug("got keyed result: %s, endpos: %s" % (result, endpos))
        #if there is no result, no key was pressed during the vm header, continue with playing vm
        #if either 5 (start playing vm immediately), 7 (delete vm), 9 (save vm), or * (exit voicemail) are pressed do something special
        if not result:
            self.onPlayVoicemail(endpos)
        elif result == '5':
            self.onPlayVoicemail(endpos)
        elif result == '7':
            self.deleteVm()
        elif result == '9':
            self.saveVm()
        elif result == '0':
            return self.onVmHelpRequest()
        elif result == '*':
            return self.agi.finish()
        else:
            self.onPlayVoicemail(endpos)

    def onPlayVoicemail(self, endpos=0, result=None):
        log.debug("In VmRetrieve onPlayVoicemail for message %s" % self.cur_msg)
        #msg = '%s/%s/%s/%s' % (vm_files_dir, self.gid, self.exten, self.message_list[self.cur_msg]['file'])
        #control stream file returns a 0 for digits if no digit is pressed, this could confuse us
        # returns (digit,endpos) on success
        vm_file = self.message_list[self.cur_msg][6]
        log.debug("Playing message %s at loc: %s" % (self.cur_msg, vm_file))
        return self.agi.controlStreamFile(vm_file, '5790*', endpos, 3, 1, 2).addCallbacks(self.onVmPlayResponse,self.onVmPlayResponseErr)

    def onVmPlayResponseErr(self, reason):
        log.debug("In VmRetrieve onVmPlayResponseErr for message %s" % self.cur_msg)
        #log.debug("streamFile returned error: %s" % reason)
        return self.agi.finish()
        #self.onVmPlayResponse(('0', 0))

    def onVmPlayResponse(self, result=None):
        log.debug("In VmRetrieve onVmPlayResponse for message %s" % self.cur_msg)
        digit_result = str(result[0])
        endpos = result[1]
        log.debug("got result: %s" % digit_result)
        msg_type = self.message_list[self.cur_msg][7]
        msg_ref = self.message_list[self.cur_msg][8]
        if msg_type == 1:
            log.debug("processing group message confirmation for group msg id: %s" % msg_ref)
            #this is a group message, mark message as confirmed
            sql = """SELECT rec_confirm FROM grp_msg WHERE id = %s""" % msg_ref
            res = execute(sql)
            res.addCallback(self.onSelectRecConfirm, msg_ref).addErrback(self.onSelectFail)
        elif msg_type == 2:
            log.debug("processing group message report for group msg id: %s" % msg_ref)
            #this is a group message report
        elif msg_type == 0:
            #this is normal voicemail
            pass
        else:
            #this is an unknown message type
            log.debug("Unknown message type found")
        if not digit_result:
            #no response from the member made while listening to voicemail
            self.tries += 1
            if self.tries == 3:
                self.onVoicemailEndErr()
            else:
                return self.agi.wait(1.0).addCallback(self.onPlayMessageInfo).addErrback(onFailure)
        elif digit_result == '0':
            #nothing was entered during the playback of the voicemail message
            self.saveVm()
        elif digit_result == '49':
            pass
        elif digit_result == '50':
            pass
        elif digit_result == '51':
            pass
        elif digit_result == '52':
            pass
        elif digit_result == '53':
            #replay preamble
            return self.agi.wait(1.0).addCallback(self.onPlayMessageInfo).addErrback(onFailure)
        elif digit_result == '54':
            pass
        elif digit_result == '55':
            #delete current message
            self.deleteVm()
        elif digit_result == '56':
            pass
        elif digit_result == '57':
            log.debug("Saving current voicemail: %s" % self.cur_msg)
            #save current message
            self.saveVm()
        elif digit_result == '48':
            #get voicemail help
            return self.agi.wait(1.0).addCallback(self.onVmHelpRequest, endpos).addErrback(onFailure)
        elif digit_result == '42':
            #cancel out of voicemail
            return self.agi.finish()
        elif digit_result =='35':
            pass
        else:
            #probably need an insequence here and a hangup then finish
            self.agi.finish()

    def onVoicemailEnd(self, result=None):
        log.debug("In VmRetrieve onVoicemailEnd for message %s" % self.cur_msg)
        msg_list = []
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_no_more'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
        return r.addCallback(self.onErrComplete).addErrback(self.onFailure)

    def onVoicemailEndErr(self, result=None):
        log.debug("In VmRetrieve onVoicemailEndErr for message %s" % self.cur_msg)
        msg_list=[]
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'hangup_1'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
        return r.addCallback(self.onErrComplete).addErrback(self.onFailure)

    def onVmHelpRequest(self, endpos=0, result=None):
        log.debug("In VmRetrieve onVmHelpRequest for message %s" % self.cur_msg)
        msg_list=[]
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_help'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 1, 1, 1, 1)
        return r.addCallback(self.onHelpResponseReply, endpos).addErrback(self.onFailure)

    def onHelpResponseReply(self, endpos=0, result=None):
        log.debug("In VmRetrieve onHelpResponseReply for message %s" % self.cur_msg)
        #handle response from help message, either no response, dtmf 1 for command list, dtmf 2 to change pin, dtmf 0 to go back to voicemail
        if not result:
            #user didn't press anything, send them back to the voicemail
            self.onPlayVoicemail(endpos)
        elif result == '1':
            #user wants to get command help
            msg_list=[]
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_commands'})
            r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
            return r.addCallback(self.onPlayVoicemail, endpos).addErrback(self.onFailure)
        elif result == '2':
            #user wants to change their pin
            return self.agi.wait(1.0).addCallback(onChangePin).addErrback(onFailure)
        elif result == '0':
            #user wants to go back to the voicemail
            self.onPlayVoicemail(endpos)
        pass

    def onChangePin(self, result=None):
        log.debug("In VmRetrieve onChangePin for message %s" % self.cur_msg)
        msg_list=[]
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_enter_new_pin'})
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 1, 8, 1, 5)
        return r.addCallback(self.onPinChangeReply, endpos).addErrback(self.onFailure)

    def onPinChangeReply(self, result=None):
        if not result:
            #no pin entered
            return self.onPlayMessageInfo()
        else:
            msg_list = []
            msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_your_pin'})
            for digit in result:
                msg_list.append({'prompt_type': 'system', 'prompt_val': '%s' % digit})
            group.groups[self.gid].changePin(self.exten, result)
            r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
            return r.addCallback(self.onPlayMessageInfo).addErrback(onFailure)
        
    def deleteVm(self, result=None):
        log.debug("In VmRetrieve deleteVm for message %s" % self.cur_msg)
        group.groups[self.gid].changeVmStatus(self.cur_vm_key, self.exten, self.cur_msg, 2)
        msg_list = []
        msg_list.append({'prompt_type': 'system', 'prompt_val': 'vm_deleted'})
        self.cur_msg += 1
        r = say(self.agi, self.gid, self.exten, self.cuid, msg_list, 0, 0, 1, 0)
        #maybe we should use the class to store the current endpos, and reset it here, instead of trying to pass it all over
        if self.cur_msg >= len(self.message_list):
            return r.addCallback(self.onVoicemailEnd).addErrback(self.onFailure)
        else:
            return r.addCallback(self.onPlayMessageInfo).addErrback(self.onFailure)

    def saveVm(self, result=None):
        log.debug("In VmRetrieve saveVm for message %s" % self.cur_msg)
        group.groups[self.gid].changeVmStatus(self.cur_vm_key, self.exten, self.cur_msg, 1)
        self.cur_msg += 1
        if self.cur_msg >= len(self.message_list):
            return self.agi.wait(1.0).addCallback(self.onVoicemailEnd).addErrback(onFailure)
        else:
            return self.agi.wait(1.0).addCallback(self.onPlayMessageInfo).addErrback(onFailure)

    def onSelectFail(self, reason):
        log.debug("recipient confirmed list check failed")

    def onSelectRecConfirm(self, result, msg_id):
        log.debug("confirming receipt of group message for message id: %s" % msg_id)
        if result == None:
            #query didn't return anything - this shouldn't happen
            log.error("request for group msg confirm list for msg record %s returned None" % msg_id)
        else:
            try:
                import json
            except:
                import simplejson as json
            #we got a valid record for confirmation list, decode it and add ourself
            confirm_list = json.loads(result[0][0])
            if self.exten not in confirm_list:
                confirm_list.append(self.exten)
                sql = """UPDATE grp_msg SET rec_confirm = '%s' WHERE id = %s""" % (json.dumps(confirm_list), msg_id)
                d = aexecute(sql)
                d.addErrback(onFailure)
            else:
                #we are already in the confirm list....  why are we here?
                log.debug("Confirm of group msg %s requested for user %s-%s while user was already in confirmed list" % (self.msg_id, self.gid, self.exten))


#normalize a US ignorized call (calls without the country code or area code)
def qualifyDial(number):
    log.debug("Qualifying External number: %s" % number)
    if len(number) < 3:
        #number is an internal extension
        result =  number
        error = None
    elif len(number) == 3:
        #number is a well-known telephony feature (i.e. 511, 911, etc.)
        result = number
        error = None
    elif len(number) == 11 and number[:1] == "1":
        #number is a fully qualified US number
        result = number
        error = None
    elif len(number) > 3 and number[:1] == "0":
        #is this an international call (designated as length > 3 and begins with a 0)
        result = number
        error = None
    elif len(number) == 10 and number[:1] in ('2','3','4','5','6','7','8','9'):
        #number is a US number missing the country code - add country code
        result = '1' + number
        error = None
    elif len(number) == 7 and number[:1] in ('2','3','4','5','6','7','8','9'):
        #number is a US number missing the country code and area code - what do we do?
        result = None
        error = 'err_need_area'
    else:
        result = None
        error = 'err_bad_ext'
    log.debug("Qualify returning value: %s, %s" % (result, error))
    return result, error

#handle playback and reaction to help files returns none or dtmf pressed during help message
def playSupportFile(agi, dialed, hostid, uid, account, cuid, gid, call_type, msg_file_list, gext, cidnum, cidname):

    def onFailure(reason):
        log.error("AGI Failure: %s" % reason.getTraceback())
        if agi:
            agi.finish()

    def onErrComplete(self, result=None):
        sequence = fastagi.InSequence()
        #sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence().addErrback(self.onFailure)
    
    def onResponse(result):
        log.debug("response result: %s" % result)

    def onReadVerifyResponse(result, agi, dialed, hostid, uid, account, cuid, gid, call_type, msg_list, tries):
        log.debug("help message got response %s for try %s" % (result, tries))
        log.debug("message list: %s" %  msg_list)
        if not result:
            tries += 1
            if tries > 2:
                if call_type == 'external':
                    msg_list=[]
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'hangup_2'})
                    result = say(agi, gid, gext, cuid, msg_list, 0, 0, 1, 0)
                    return result.addCallback(onErrComplete).addErrback(onFailure)
                elif call_type == 'internal':
                    msg_list=[]
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'hangup_2'})
                    result = say(agi, gid, gext, cuid, msg_list, 0, 0, 1, 0)
                    return result.addCallback(onErrComplete).addErrback(onFailure)
                else:
                    #strange unknown call type
                    log.debug("Unknown call type: %s" % call_type)
            else:
                r = say(agi, gid, gext, cuid, msg_list[:], 1, 2, 1, 2)
                return r.addCallback(onReadVerifyResponse, agi, dialed, hostid, uid, account, cuid, gid, call_type, msg_list[:], tries)
        else:
            dtmf = result
            routeInternal(agi, dialed, hostid, uid, dtmf, account, cuid, gid, call_type, gext, cidnum, cidname)

    tries = 0
    msg_list = []
    for msg_file in msg_file_list:
        msg_list.append({'prompt_type': 'system', 'prompt_val': '%s' %  msg_file})
    r = say(agi, gid, gext, cuid, msg_list[:], 1, 2, 1, 2)
    return r.addCallback(onReadVerifyResponse, agi, dialed, hostid, uid, account, cuid, gid, call_type, msg_list[:], tries)

#play a message to a channel
def say(agi, gid, exten, cuid, msg_list, msg_type, resp_len, max_tries, timeout, play_msg=1):
    #creates a prompt from the msg_list, and then plays it back to the provided agi channel
    #if msg_type = 0 message is played in full, if msg_type = 1 message is played until a response is received
    #resp_len defines how many dtmf characters are expected if msg_type = 1
    #tries defines maximum number of attempts
    #message list is a list of dictionaries in reverse order.  We need to reverse it to get the correct order.
    #each dictionary in the message list has two entries, prompt_type and prompt_val.
    #prompt_type is the type of message (full text or list of alphanumerics that need to be spoken individually)
    #prompt_type is either 'system', 'user', 'group', 'alphanum', or 'location'.  location type provides a system location for a file to be played
    #prompt_val is the text to be spoken
    def onFailure(reason):
        if agi:
            agi.finish()
        #log.debug("failure: %s" % reason)
    def say_alpha_numeric(gid, exten, text_string, voice):
        msg_alpha = ''
        msg_alpha_count = 0
        for alpha in text_string:
            msg_alpha += '%s/%s/raw/%s' % (system_sounds_dir, voice, alpha)
            if not checkExist(msg_alpha):
                log.debug('file not available: %s' % msg_alpha)
                #get the language fallback personality
                fallback_voice = group.groups[gid].getVoicePersonality(exten, 1)
                msg_alpha += '%s/%s/raw/%s' % (system_sounds_dir, fallback_voice, alpha)
                if not checkExist(msg_alpha):
                    log.debug('file not available: %s' % msg_alpha)
                    #get the MASTER fallback personality
                    master_voice = group.groups[gid].getVoicePersonality(exten, 2)
                    msg_alpha += '%s/%s/raw/%s' % (system_sounds_dir, master_voice, alpha)
                    if not checkExist(msg_alpha):
                        log.debug("MASTER file missing for %s" % msg_alpha)
            msg_alpha_count += 1
            if msg_alpha_count < len(text_string):
                msg_alpha += '&'
        return msg_alpha
    def say_main(text_string):
        return '%s' % text_string
    def say_system(text_string, gid, ext, voice):
        log.debug("Using personality %s" % voice)
        msg_sys = '%s/%s/raw/%s' % (system_sounds_dir, voice, text_string)
        if not checkExist(msg_sys):
                log.debug('file not available: %s' % msg_sys)
                #get the language fallback personality
                fallback_voice = group.groups[gid].getVoicePersonality(ext, 1)
                msg_sys = '%s/%s/raw/%s' % (system_sounds_dir, fallback_voice, text_string)
                if not checkExist(msg_sys):
                    log.debug('file not available: %s' % msg_sys)
                    #get the MASTER fallback personality
                    master_voice = group.groups[gid].getVoicePersonality(ext, 2)
                    msg_sys = '%s/%s/raw/%s' % (system_sounds_dir, master_voice, text_string)
                    if not checkExist(msg_sys):
                        log.debug("MASTER file missing for %s" % msg_sys)
        return msg_sys
    def say_user(gid, exten, text_string):
        return '%s/%s/%s/%s' % (group_sounds_dir, gid, exten, text_string)
    def say_group(gid, text_string):
        return '%s/%s/%s' % (group_sounds_dir, gid, text_string)
    def say_loc(text_string):
        return '%s' % text_string
    def msg_played(result, agi, gid, exten, msg, max_tries, tries, timeout):
        #log.debug("played message %s" % msg)
        return None
    def msg_playback(result, agi, gid, exten, msg, max_tries, tries, timeout, resp_len):
        log.debug("playing uninterrupted message: %s" % msg)
        return agi.playback(str(msg)).addCallback(msg_played, agi, gid, exten, msg, max_tries, tries, timeout).addErrback(onFailure)
    def msg_play_read(result, agi, gid, exten, msg, max_tries, tries, timeout, resp_len):
        log.debug("reading message: %s" % msg)
        return agi.execute('Read', 'agi_read_response', msg, resp_len, 's', 1, timeout).addCallback(msg_read, agi, gid, exten, msg, max_tries, tries, timeout, resp_len).addErrback(onFailure)
    def msg_read(result, agi, gid, exten, msg, max_tries, tries, timeout, resp_len):
        #log.debug("collecting read_response")
        return agi.getVariable('agi_read_response').addCallback(msg_read_response, agi, gid, exten, msg, max_tries, tries, timeout, resp_len).addErrback(onFailure)
    def msg_read_response(result, agi, gid, exten, msg, max_tries, tries, timeout, resp_len):
        tries += 1
        log.debug("got result: %s for try %s of max tries %s" % (result, tries, max_tries))
        if tries < max_tries:
            if result:
                log.debug("returning result: %s" % result)
                call.calls[cuid].logDtmfEvent(result)
                return result
            elif timeout > 0:
                #no result from the read, keep listening during specified timeout
                return agi.execute('Read', 'agi_read_response', 'silence/%s' % timeout, resp_len, 's', 1, 1).addCallback(msg_play_read, agi, gid, exten, msg, max_tries, tries, timeout, resp_len).addErrback(onFailure)
            else:
                #no specified timeout, and tries not exceeded, so play message again
                return agi.execute('Read', 'agi_read_response', msg, resp_len, 's', 1, 0).addCallback(msg_play_read, agi, gid, exten, msg, max_tries, tries, timeout, resp_len).addErrback(onFailure)
        elif tries >= max_tries:
            if result:
                log.debug("returning result: %s" % result)
                call.calls[cuid].logDtmfEvent(result)
                return result
            else:
                return None
        else:
            #max tries exceeded
            log.debug("too many tries, returning no result")
            return None
    def say_play(result, agi, gid, exten, cuid, msg_list, msg_type, resp_len, max_tries, timeout, msg, tries):
        msg = str(msg)
        if msg_type == 0:
            #playback
            log.debug("executing playback of message: %s" % msg)
            res = msg_playback(None, agi, gid, exten, msg, max_tries, tries, timeout, resp_len)
            return res
        elif msg_type == 1:
            log.debug("executing read of message: %s" % msg)
            res = msg_play_read(None, agi, gid, exten, msg, max_tries, tries, timeout, resp_len)
            return res
        else:
            #log.debug("unknown message type")
            return 0
    def checkExist(msg_loc):
        def statFile(file_loc):
            try:
                tmp = os.stat(file_loc)
                exist = True
            except:
                log.debug("requested file not found: %s" % msg)
                exist = False
            return exist
        def checkAndCache(msg_loc, file_loc):
            file_exist = statFile(file_loc)
            if file_exist:
                log.debug("Returning NEW file loc")
                system_sounds_exist_cache[msg_loc] = int(time.time())
            return file_exist
        def checkWithCache(msg_loc, file_loc):
            cache_time = system_sounds_exist_cache[msg_loc]
            if int(time.time() - cache_time) < system_sounds_exist_cache_time:
                log.debug("Returning CACHED file loc")
                return True
            else:
                return checkAndCache(msg_loc, file_loc)
        file_loc = '%s.sln' % msg_loc
        if msg_loc in system_sounds_exist_cache:
            return checkWithCache(msg_loc, file_loc)
        else:
            return checkAndCache(msg_loc, file_loc)
    
    log.debug("Say called with agi: %s, list: %s, type: %s, len: %s, tries: %s, timeout: %s, play: %s" % (agi, msg_list, msg_type, resp_len, max_tries, timeout, play_msg))
    #log.debug("In say routine with msg_list %s" % msg_list)
    #iterate through the msg_list to create the full message
    #first we need to reverse the list, as normally python lists are lifo, reversing it will make it a fifo list
    msg_list.reverse()
    msg = ''
    voice = group.groups[gid].getVoicePersonality(exten, 0)
    while len(msg_list) > 0:
        msg_fragment = msg_list.pop()
        msg_prompt_type = msg_fragment['prompt_type']
        msg_text = msg_fragment['prompt_val']
        if msg_prompt_type == 'system':
            log.debug("handling system say fragment: %s" % msg_text)
            msg_loc = say_system(msg_text, gid, exten, voice)
            log.debug("done handling system say fragment: %s" % msg_text)
        elif msg_prompt_type == 'user':
            msg_loc = say_user(gid, exten, msg_text)
        elif msg_prompt_type == 'group':
            msg_loc = say_group(gid, msg_text)
            log.debug("group message loc built: %s" % msg_loc)
        elif msg_prompt_type == 'location':
            msg_loc = say_loc(msg_text)
        elif msg_prompt_type == 'alphanumeric':
            msg_loc = say_alpha_numeric(gid, exten, msg_text, voice)
        elif msg_prompt_type == 'main':
            msg_loc = say_main(msg_text)
        msg += msg_loc
        if len(msg_list) > 0:
            msg += '&'
        log.debug("message: %s" % msg)
    #Now that we have the message built, we can have the channel play the message
    log.debug("finished building message: %s, checking existence" % msg)
    if play_msg:
        tries = 0
        r = agi.answer().addCallback(say_play, agi, gid, exten, cuid, msg_list, msg_type, resp_len, max_tries, timeout, msg, tries)
        return r
    else:
        return msg


#handle lack of a valid response
def onResponseFailure(error):
    log.error(error)

#handle failure of agi call
def onFailure(error):
    log.error("received error")
    log.error(error)
