<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Home</%def>

<%block name="body_content">
<div id="alert-area"></div>
<div class="container-fluid">
      <div class="row-fluid">
        <div class="span3">
          <div class="well sidebar-nav-fixed">
            	<ul class="nav nav-list">
			        <%include file="./global_menu.mako"/>
				</ul>
          </div><!--/.well -->
        </div><!--/span-->
        <div class="span9">
          <div class="row-fluid">
            <div>
				<h3 class="subHeading"><i>${self.title()}</i>
					<%block name="subHeading"/>
				</h3>
	            <div class="DetailView">
			    	<%block name="DetailView"/>
			    </div>
            </div>
          </div><!--/row-->
        </div><!--/span-->
      </div><!--/row-->
      
	<script> 
		function newAlert (success, message) {
			if (success == true ){
				$("#alert-area").append($("<div class='alert alert-success alert-message'><a class='close' data-dismiss='alert'>×</a><strong>Success! </strong>"+message+"</div>"));
			}
			else{
				$("#alert-area").append($("<div class='alert alert-error alert-message'><a class='close' data-dismiss='alert'>×</a><strong>Success! </strong>"+message+"</div>"));
			}					
			
		    $(".alert-message").delay(5000).fadeOut("slow", function () { $(this).remove(); });
		}
	</script>
</%block>