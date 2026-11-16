{% materialization external_table, adapter='postgres' %}
  {%- set target_relation = this.incorporate(type='table') -%}

  {{ adapter.create_schema(target_relation) }}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}

  {% call statement('main') -%}
    {{ sql }}
  {%- endcall %}

  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}