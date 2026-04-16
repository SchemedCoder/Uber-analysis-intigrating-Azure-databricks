SELECT c.city_name, COUNT(*) AS rides
FROM fact_rides f
JOIN dim_city c ON f.city_id = c.city_id
GROUP BY c.city_name;

SELECT city_id,
       COUNT(*) AS rides,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS rank
FROM fact_rides
GROUP BY city_id;
