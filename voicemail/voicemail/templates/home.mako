<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Home</%def>

<%block name="body_content">

<div class="container-fluid">
      <div class="row-fluid">
        <div class="span3">
          <div class="well sidebar-nav">
            	<ul class="nav nav-list">
            		<li class="nav-header">Options</li>
			        %if utils.has_permission('admin'):
			        <li> <a href="/user/add"> Add user </a> </li>
			        <li> <a href="/users/list"> User Configuration </a> </li>
			        %endif
			        <li> <a href="/vm/view"> Voicemails </a> </li>  
			        <li> Search </li>
			        <li class="nav-header">Global Actions</li>
			        <%include file="./global_menu.mako"/>
				</ul>
          </div><!--/.well -->
        </div><!--/span-->
        <div class="span9">
          <div class="row-fluid">
            <div>
	            <div class="main_content"">
			    	<h3><img src="${request.static_url('voicemail:static/img/voicemail.gif')}" style="vertical-align:middle" alt="" />VoiceMail Access - ${self.title()}</h3>
			    	<%block name="main_content"/>
			    </div>
            </div>
          </div><!--/row-->
        </div><!--/span-->
      </div><!--/row-->
</%block>