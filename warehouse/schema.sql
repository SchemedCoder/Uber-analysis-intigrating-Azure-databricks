CREATE TABLE fact_rides (
    ride_id INT,
    city_id INT,
    time_id INT,
    distance_km FLOAT,
    base_fare FLOAT,
    surge_multiplier FLOAT
);

CREATE TABLE dim_city (
    city_id INT,
    city_name VARCHAR(50)
);

CREATE TABLE dim_time (
    time_id INT,
    hour INT,
    day INT,
    month INT,
    year INT
);
