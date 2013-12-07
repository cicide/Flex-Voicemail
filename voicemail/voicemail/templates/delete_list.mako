
<div id="delete_modal" class="modal hide fade in" style="display: none; ">  
	<div class="modal-header">  
		<a class="close" data-dismiss="modal">×</a>  
		<h3>Delete list <span id="listname"></span> </h3>  
		</div>  
		<div class="modal-body">  
		<p>Please Confirm? This cannot be undone</p>
		<input type="hidden" name="listid" id="listid" value=""/>                
	</div>  
	<div class="modal-footer">  
		<button class="btn btn-primary" onclick="handleClick('/list/delete')" data-dismiss="modal">Delete</button>  
		<button class="btn" data-dismiss="modal">Close</button>  
	</div>
</div>
<script>
	function handleClick(url) {
		  
		  var url = this.location.origin + url;
		  data = {'listid': $('#listid').val()}
		  $.post(url, data, function(response) {
	  			newAlert(response.success, response.msg);
	  			window.setTimeout(function(){location.reload()},3000)
			}, 'json');
	}
    function showModal(listid,listname){
        $('#listid').val(listid);
        $('#listname').replaceWith(listname);
        $('#delete_modal').modal('show');
    }
</script>
