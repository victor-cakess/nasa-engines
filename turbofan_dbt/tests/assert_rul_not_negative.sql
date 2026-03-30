select *
from {{ ref('fct_training_features') }}
where rul < 0
