<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Edit List</%def>
<%block name="DetailView">
	<div id="details">
	        %if form:
	          ${form|n}
	        %endif
	    <script type="text/javascript">
	        deform.load()
	    </script>
	</div>
</%block>
