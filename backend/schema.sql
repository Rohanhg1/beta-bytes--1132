CREATE TABLE hospitals (
    hospital_id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255) NOT NULL,
    specialization VARCHAR(255) NOT NULL,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,
    longitude DECIMAL(10, 6) NOT NULL,
    rating DECIMAL(2, 1),
    email VARCHAR(255)
);

-- Example Data Insert
INSERT INTO hospitals (hospital_name, specialization, state, district, latitude, longitude, rating, email)
VALUES 
('Apollo Hospital', 'Cardiologist', 'Karnataka', 'Mysore', 12.300000, 76.650000, 4.5, 'apollo.mysore@example.com'),
('City Care', 'Dentist', 'Karnataka', 'Mysore', 12.310000, 76.660000, 4.2, 'citycare.mys@example.com');
