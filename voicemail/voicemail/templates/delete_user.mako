
<div id="delete_modal" class="modal hide fade in" style="display: none; ">  
	<div class="modal-header">  
		<a class="close" data-dismiss="modal">×</a>  
		<h3>Delete user <span id="username"></span> </h3>  
		</div>  
		<div class="modal-body">  
		<p>Please Confirm? This cannot be undone</p>
		<input type="hidden" name="userid" id="userid" value=""/>                
	</div>  
	<div class="modal-footer">  
		<button class="btn btn-primary" onclick="handleClick('/user/delete')" data-dismiss="modal">Delete</button>  
		<button class="btn" data-dismiss="modal">Close</button>  
	</div>
</div>
<script>
	function handleClick(url) {
		  
		  var url = this.location.origin + url;
		  data = {'userid': $('#userid').val()}
		  $.post(url, data, function(response) {
	  			newAlert(response.success, response.msg);
	  			window.setTimeout(function(){location.reload()},5000)
			}, 'json');
		}
    function showModal(userid,username){
        $('#userid').val(userid);
        $('#username').replaceWith(username);
        $('#delete_modal').modal('show');
    };
</script>
