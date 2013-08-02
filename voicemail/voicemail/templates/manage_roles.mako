<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Manage Admins</%def>

<%block name="subHeading">
<a class="btn btn-small pull-right" href="/">Back</a>
</%block>
<%block name="DetailView">
	<div id="details">
		
		<table class="table">
			<tr>
				<th>ID</th>
				<th>Name</th>
				<th>Username</th>
				<th>Extension</th>
				<th>Pin</th>
				<th>Admin</th>
			</tr>
			% for user in users:
			<tr>
	        	<td>${user.id}</td>
	        	<td>${user.name}</td>
	        	<td>${user.username}</td>
	        	<td>${user.extension}</td>
	        	<td>${user.pin}</td>
	        	%if user == request.user:
        			<td><input type="checkbox" value="${user.id}" disabled checked="checked" onclick="handleClick(this);">
	        	%elif utils.is_admin(user):
	        		<td><input type="checkbox" value="${user.id}" checked="checked" onclick="handleClick(this);">
	        	%else:
	        		<td><input type="checkbox" value="${user.id}" onclick="handleClick(this);">
	        	%endif
	        </tr>
			% endfor
		</table>
	</div>
	
	<script>
		function handleClick(cb) {
		  
		  var url = this.location.origin + '/admin/edit';
		  data = {'userid': cb.value,'admin':cb.checked}
		  $.post(url, data, function(response) {
	  			newAlert(response.success, response.msg);
			}, 'json');
			
		}
		
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