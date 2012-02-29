create table users (
id int(11) not NULL auto_increment COMMENT 'Unique id for the user in the vm system',
extension varchar(10) not  NULL Comment 'Extension in the asterisk system',
pin varchar(10) not NULL Comment 'Pin for the user to access the VM',
name varchar(80) Comment 'Name of the user',
create_date datetime NOT NULL COMMENT 'When the user was created',
status int(3) NOT NULL COMMENT 'Active or not'
) engine=innodb;

create table voicemails (
id int(11) not NULL auto_increment COMMENT 'Unique id for the vm',
user_id int(11) not NULL COMMENT 'user id to whom the vm belongs',
duration int(7) not NULL COMMENT 'duration of voicemail in milliseconds',
create_date datetime NOT NULL COMMENT 'date time when the vm was left',
path varchar(256) NOT NULL COMMENT 'path to the vm',
is_read tinyint(1) not NULL COMMENT 'read = 0, unread = 1',
status int(3) not NULL COMMENT 'status whether deleted or not. May hold more statues',
deleted_on datetime COMMENT 'date when this was deleted',
cid_name varchar(80) COMMENT 'CallerID name of the person leaving VM',
cid_number varchar(20) COMMENT 'CallerID for the person leaving VM'
) engine = innodb;

create table user_vm_prefs (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
user_id int(11) not NULL Comment 'user id for this record',
folder varchar(100) not NULL COMMENT 'path to the vm folder',
deliver_vm tinyint(1) default '0' COMMENT '0 - donotdeliver, 1 - deliver',
attach_vm tinyint(1) default '0' COMMENT '0 - donot attach, 1 - attach',
notification_method int(3) COMMENT '1-email, 2-sms',
email varchar(100) COMMENT 'this is where the vms will be emailed',
sms_addr varchar(80) COMMENT ' SMS address',
ivr_tree int(11) COMMENT 'which ivr to use id of the entry point in ivr table',
vm_greeting varchar(100) COMMENT 'Path to the greeting recording',
vm_name_recording varchar(100) COMMENT 'path to the recorded name',
greeting_prompt_id int(11) COMMENT 'prompt id for the greeting'
) engine = innodb;

create table ivr_tree (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
parent_id int(11) COMMENT 'parent id for this entry point',
current_prompt_id int(11) COMMENT 'prompt to play when this step is being executed',
parent_prompt_id int(11) COMMENT 'prompt to play when the parent is annoucing this step',
dtmf_len int(5) COMMENT 'no of dtmf keys to accept for this step',
dtmf_key char(1) COMMENT 'Which key results in this option from the parent',
timeout int(5) COMMENT 'time to wait for input in ms',
is_interruptable tinyint(1) COMMENT 'Can the prompt be interrupted'
) engine = innodb;

create table prompts (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
name varchar(40) not NULL COMMENT 'Name for the prompt'
) engine = innodb;

create table prompt_details (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
prompt_id varchar(40) not NULL COMMENT 'id for the prompt',
sequence_number int(8) not NULL COMMENT 'sequence number in the prompt for this particular part',
prompt_type int(3) NOT NULL COMMENT 'type of this prompt 1 - static file, 2 - Text-to-Speech, 3 - use User/group vm_greeting, 4 - use User/group name_recording',
path varchar(100) COMMENT 'path for type 1',
delay_before int(4) COMMENT 'delay x ms before the prompt',
delay_after int(4) COMMENT 'delay x ms after the prompt'
) engine = innodb;

create table groups (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
name varchar(40) NOT NULL COMMENT 'name of the group'
) engine = innodb;

create table user_groups (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
user_id int(11) not NULL COMMENT 'User id for the user record',
group_id int(11) not NULL COMMENT 'Group to which the user belongs',
primary_group tinyint(1) COMMENT 'Is this the primary group for the user'
) engine = innodb;

create table group_vm_prefs (
id int(11) not NULL auto_incerment COMMENT 'Unique id for the record',
group_id int(11) not NULL Comment 'group id for this record',
folder varchar(100) not NULL COMMENT 'path to the vm folder',
deliver_vm tinyint(1) default '0' COMMENT '0 - donotdeliver, 1 - deliver',
attach_vm tinyint(1) default '0' COMMENT '0 - donot attach, 1 - attach',
notification_method int(3) COMMENT '1-email, 2-sms',
email varchar(100) COMMENT 'this is where the vms will be emailed',
sms_addr varchar(80) COMMENT ' SMS address',
ivr_tree_id int(11) COMMENT 'which ivr to use id of the entry point in ivr table',
vm_greeting varchar(100) COMMENT 'Path to the greeting recording',
vm_name_recording varchar(100) COMMENT 'path to the recorded name'
) engine = innodb;
