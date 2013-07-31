<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Edit User</%def>
<%block name="main_content">
	<div id="details">
	        %if form:
	          ${form|n}
	        %endif
	    <script type="text/javascript">
	        deform.load()
	    </script>
	</div>
</%block>
