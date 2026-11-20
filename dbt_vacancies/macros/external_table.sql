{% materialization external_table, adapter='postgres' %}
  {%- set target_relation = this.incorporate(type='table') -%}

  {{ adapter.create_schema(target_relation) }}

  -- Run pre-hooks in both transaction contexts so that model-level
  -- config(pre_hook=...) hooks (which default to transaction=True)
  -- are executed, matching the behavior of the built-in table
  -- materialization.
  {{ run_hooks(pre_hooks, inside_transaction=False) }}
  {{ run_hooks(pre_hooks, inside_transaction=True) }}

  {% call statement('main') -%}
    {{ sql }}
  {%- endcall %}

  -- Post-hooks likewise run in both contexts.
  {{ run_hooks(post_hooks, inside_transaction=True) }}
  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}