<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8" />
        <title>VoiceMail Access - ${self.title()}</title>
        
        <script type="text/javascript" src="${request.static_url('voicemail:static/js/jquery-1.9.1.min.js')}"></script>
        <link href="${request.static_url('voicemail:static/css/jquery-ui.min.css')}" media="all" rel="stylesheet" type="text/css" />
        <link href="${request.static_url('voicemail:static/css/style.css')}" media="all" rel="stylesheet" type="text/css" />
        <link href="${request.static_url('voicemail:static/css/voicemail.css')}" media="all" rel="stylesheet" type="text/css" />
        <script type="text/javascript" src="${request.static_url('voicemail:static/js/jquery-ui-1.10.2.min.js')}"></script>
</head>
<body>

        <div class="wrapper">
            ${render_flash_messages()|n}
            % if request.user:
            <div class="header">
                        <h1 class="logo"><img src="${request.static_url('voicemail:static/img/voicemail.gif')}" style="vertical-align:middle" alt="" />VoiceMail Access - ${self.title()}</h1>
                        <div class="userinfo">
                                <h6>Welcome - ${request.user.name}</h6>
                                <a href="${request.route_url('logout')}">Logout</a>
                        </div>
            </div>
                <div class="left_col">
                        <div class='left_list'>
                                <h3>Options</h3>
                        </div>

                        <div class='left_list'>
                            <%include file="./global_menu.mako"/>
                        </div>

            </div>
            %endif


        ${self.body()}
        </div>

      <div id="footer">
          <em>VoiceMail Access</em>
      </div>
    </body>
</html>

