{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {# In a normal dbt setup, we have a schema defined inside the local profiles.yml which gets appended like this: {{target.schema}}_{{ custom_schema_name | trim }}; for local convenience we define it simplified like below #}
        {{ custom_schema_name | trim }} 
    {%- endif -%}
{%- endmacro %}
