CREATE PROCEDURE GetTopCities
AS
BEGIN
    SELECT TOP 5 city_id, COUNT(*) AS total_rides
    FROM fact_rides
    GROUP BY city_id
    ORDER BY total_rides DESC;
END;
