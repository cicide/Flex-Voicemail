drop index username on users;
alter table users modify username varchar(100) COMMENT 'login user id could be email';

