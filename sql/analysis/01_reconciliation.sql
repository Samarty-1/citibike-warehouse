-- Every staged trip lands in fct_trips exactly once, and what each data-quality
-- flag covers. Analyses use valid trips: docked at both ends, resolvable
-- stations, 1 minute to 24 hours long.
select
    system,
    (select count(*) from stg_trips s where s.system = f.system)       as staged,
    count(*)                                                            as in_fact,
    count(*) filter (where is_dockless)                                 as dockless,
    count(*) filter (where is_unresolved_station)                       as unresolved_station,
    count(*) filter (where is_bad_duration)                             as bad_duration,
    count(*) filter (where not (is_dockless or is_unresolved_station or is_bad_duration))
                                                                        as valid
from fct_trips f
group by system
order by system desc;
