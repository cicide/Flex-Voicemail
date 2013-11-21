<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Add List</%def>

<%block name="DetailView">
	    %if form:
          ${form|n}
        %endif
    <script type="text/javascript">
        deform.load();
    </script>
</%block>
