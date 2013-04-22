<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Login</%def>
<div id="details">
    <div class="login">
        <p>
            %if form:
              ${form|n}
            %endif
        </p>
        <script type="text/javascript">
            deform.load()
        </script>
    </div>
</div>
