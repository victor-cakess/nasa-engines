select *
from {{ ref('fct_training_features') }}
where rul_capped > 125
