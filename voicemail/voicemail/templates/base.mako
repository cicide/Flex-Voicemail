<!DOCTYPE html>
 <!-- The layout macro below is what is referenced in the layouts.Laytouts.global_template -->
<html lang="en" metal:define-macro="layout">
  <head>

    <!-- Styles from Deform Bootstrap -->
    <link rel="stylesheet" href="${request.static_url('deform_bootstrap:static/deform_bootstrap.css')}" type="text/css" media="screen" charset="utf-8" />
    <link rel="stylesheet" href="${request.static_url('deform_bootstrap:static/chosen_bootstrap.css')}" type="text/css" media="screen" charset="utf-8" />
    <link rel="stylesheet" href="${request.static_url('deform:static/css/ui-lightness/jquery-ui-1.8.11.custom.css')}" type="text/css" media="screen" charset="utf-8" />
  </head>

  <body>
  	<div class="navbar navbar-fixed-top">
      <div class="navbar-inner">
        <div class="container-fluid">
	      <a class="btn btn-navbar" data-toggle="collapse" data-target=".nav-collapse">
	        <span class="icon-bar"></span>
	        <span class="icon-bar"></span>
	        <span class="icon-bar"></span>
	      </a>
	      <a class="brand" href="${request.application_url}">FlexVoiceMail</a>
	      %if request.user:
		      <div class="btn-group pull-right">
		        <a class="btn dropdown-toggle" data-toggle="dropdown" href="#">
		          <i class="icon-user icon-white"></i> 
		          	${request.user.name}
		          <span class="caret"></span>
		        </a>
		        <ul class="dropdown-menu">
		          <li><a href="${request.application_url}/logout">Sign Out</a></li>
		        </ul>
		      </div>
		  %else:
	      <div tal:condition="request.user is None" class="pull-right">
	        <a class="btn" href="${request.application_url}/login">Sign In
	        </a>
	      </div>
	      %endif
	      <div class="nav-collapse">
            <ul class="nav">
              <li><a href="${request.application_url}">Home</a></li>
              <li><a href="${request.application_url}/about/">About</a></li>
            </ul>
          </div><!--/.nav-collapse -->
        </div>
      </div>
    </div>
    
    <div class="body_content" style="padding-top: 60px;">
            <%block name="body_content"/>
    </div>
    
    <hr>

      <footer>
        <p>&copy; FlexVoicemail 2012</p>
        <p class="pull-right">
          small image
        </p>
      </footer>

    </div><!--/.fluid-container-->

    <!-- The javascript resources from Deform -->
    <script src="${request.static_url('deform:static/scripts/jquery-1.7.2.min.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/jquery-ui-1.8.18.custom.min.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/jquery-ui-timepicker-addon-0.9.9.js')}"></script>
    <script src="${request.static_url('deform:static/scripts/deform.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/deform_bootstrap.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/bootstrap.min.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/bootstrap-datepicker.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/bootstrap-typeahead.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/jquery.form-2.96.js')}"></script>
    <script src="${request.static_url('deform_bootstrap:static/jquery.maskedinput-1.3.js')}"></script>
  </body>
</html>