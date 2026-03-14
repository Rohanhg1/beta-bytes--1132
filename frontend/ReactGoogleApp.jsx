import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, Marker, InfoWindow } from '@react-google-maps/api';

// ==========================================
// FEATURE 11 - REQUIRED APIs (Google Maps API, Places, Speech)
// ==========================================

const GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE";
const libraries = ['places'];

const mapContainerStyle = {
    width: '100%',
    height: '100%'
};

const defaultCenter = { lat: 20.5937, lng: 78.9629 }; // India Center

const INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", 
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", 
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
];

export default function GeoVoiceSmartClinic() {
    const { isLoaded, loadError } = useJsApiLoader({
        googleMapsApiKey: GOOGLE_MAPS_API_KEY,
        libraries: libraries,
    });

    const [map, setMap] = useState(null);
    const [stateName, setStateName] = useState('Karnataka');
    const [districtName, setDistrictName] = useState('Shivamogga');

    const [hospitals, setHospitals] = useState([]);
    const [selectedHospital, setSelectedHospital] = useState(null);
    
    // FEATURE 8 - BOOKING SYSTEM
    const [appointments, setAppointments] = useState([]);

    const accumulatorRef = useRef([]);
    const activeSearchesRef = useRef(0);
    const hasInitialLoaded = useRef(false);

    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef(null);

    const onLoad = useCallback(function callback(mapInstance) {
        setMap(mapInstance);
    }, []);

    const onUnmount = useCallback(function callback() {
        setMap(null);
    }, []);

    // Perform an initial load on component mount so Shivamogga clinics show up immediately
    useEffect(() => {
        if (map && districtName && stateName && !hasInitialLoaded.current) {
            hasInitialLoaded.current = true;
            searchDistrictLocation(districtName, stateName);
        }
    }, [map]); // Only run when map instance is ready

    // ==========================================
    // FEATURE 1, 9 - DYNAMIC GEOCODING FOR ANY DISTRICT
    // ==========================================
    const searchDistrictLocation = (district, state, autoSpokenName = "", autoSpecialization = "") => {
        if (!map) return;
        const geocoder = new window.google.maps.Geocoder();
        const query = `${district}, ${state}, India`;
        
        geocoder.geocode({ address: query }, (results, status) => {
            if (status === 'OK' && results[0]) {
                const location = results[0].geometry.location;
                // FEATURE 1 - Map must move to district center
                map.panTo(location);
                map.setZoom(12);
                fetchAllHealthcare(location, autoSpokenName, autoSpecialization);
            } else {
                alert("Could not locate district: " + query);
            }
        });
    };

    const handleManualSearch = () => {
        if (districtName) {
            searchDistrictLocation(districtName, stateName);
        } else {
            alert("Please enter a district name.");
        }
    };

    // ==========================================
    // FEATURE 2, 4, 10 - SHOW ALL HOSPITALS + CLINICS
    // ==========================================
    const fetchAllHealthcare = (latLng, autoSpokenName = "", autoSpecialization = "") => {
        setHospitals([]);
        accumulatorRef.current = [];
        const service = new window.google.maps.places.PlacesService(map);

        // FEATURE 2 & 10 - Search types and keywords
        const searchQueries = [
            { type: 'hospital' },
            { type: 'doctor' },
            { type: 'health' },
            { keyword: 'clinic' }
        ];

        activeSearchesRef.current = searchQueries.length;

        searchQueries.forEach(query => {
            const request = {
                location: latLng,
                radius: 50000, // FEATURE 2 - Use large radius: 50000
                ...query
            };

            const searchCallback = (results, status, pagination) => {
                if (status === window.google.maps.places.PlacesServiceStatus.OK && results) {
                    
                    // Filter duplicates based on place_id just in case queries overlap
                    const newResults = results.filter(r => !accumulatorRef.current.some(existing => existing.place_id === r.place_id));
                    accumulatorRef.current = [...accumulatorRef.current, ...newResults];
                    setHospitals([...accumulatorRef.current]);

                    // FEATURE 4 - LOAD ALL RESULTS USING PAGINATION
                    if (pagination && pagination.hasNextPage) {
                        setTimeout(() => {
                            pagination.nextPage();
                        }, 2000);
                    } else {
                        checkIfAllComplete();
                    }
                } else {
                    checkIfAllComplete();
                }
            };

            const checkIfAllComplete = () => {
                activeSearchesRef.current -= 1;
                if (activeSearchesRef.current === 0) {
                    console.log(`Complete! Loaded ${accumulatorRef.current.length} total healthcare facilities.`);
                    if (autoSpokenName || autoSpecialization) {
                        determineBestHospital(autoSpokenName, autoSpecialization, accumulatorRef.current);
                    }
                }
            };

            service.nearbySearch(request, searchCallback);
        });
    };

    // ==========================================
    // FEATURE 5 - VOICE INPUT & PARSING
    // ==========================================
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.lang = 'en-IN';
            recognitionRef.current.continuous = false;

            recognitionRef.current.onresult = (event) => {
                const transcript = event.results[0][0].transcript.toLowerCase();
                processVoiceCommand(transcript);
                setIsListening(false);
            };

            recognitionRef.current.onerror = () => setIsListening(false);
            recognitionRef.current.onend = () => setIsListening(false);
        }
    }, [hospitals, map, stateName, districtName]);

    const processVoiceCommand = (text) => {
        console.log("Transcript:", text);
        
        let specialization = "";
        const specs = ["dentist", "dermatologist", "cardiologist", "neurologist", "orthopedic", "pediatrician", "gynecologist", "oncologist", "ophthalmologist"];
        specs.forEach(s => { if (text.includes(s)) specialization = s; });

        let spokenHospitalName = "";
        // Extract hospital name: "book apollo hospital" -> "apollo"
        const bookMatch = text.match(/(?:book|find|need) (.*?)( hospital| clinic| in |$)/);
        if (bookMatch && bookMatch[1] && !specs.includes(bookMatch[1].trim())) {
            spokenHospitalName = bookMatch[1].trim();
        }

        let extractedDistrict = "";
        const inMatch = text.match(/in ([a-z\s]+)/);
        if (inMatch && inMatch[1]) {
            extractedDistrict = inMatch[1].trim();
        }

        console.log("Extracted Voice Entities:", { extractedDistrict, spokenHospitalName, specialization });

        // Change district if new one recognized
        if (extractedDistrict && extractedDistrict !== districtName.toLowerCase()) {
            setDistrictName(extractedDistrict);
            // Initiate full pipeline: geocode -> pan -> search places -> find best hospital
            searchDistrictLocation(extractedDistrict, stateName || "India", spokenHospitalName, specialization);
        } else {
            // Already in district or none specified, just find from currently loaded
            determineBestHospital(spokenHospitalName, specialization, accumulatorRef.current);
        }
    };

    const determineBestHospital = (spokenName, specialization, allHospitals) => {
        if (!allHospitals.length) {
            alert("No hospitals loaded. Please search the district first.");
            return;
        }

        let bestMatch = null;

        // FEATURE 6 - IF HOSPITAL NAME GIVEN
        if (spokenName && spokenName.length > 2) {
            // Find EXACT or partial match
            bestMatch = allHospitals.find(h => h.name.toLowerCase().includes(spokenName)) || 
                        allHospitals.find(h => h.name.toLowerCase().includes(spokenName.split(' ')[0]));
            
            if (bestMatch) {
                console.log("Matched specific hospital:", bestMatch.name);
            }
        }

        // FEATURE 7 - IF HOSPITAL NAME NOT GIVEN
        if (!bestMatch) {
            // Filter by specialization/type if requested
            let candidates = allHospitals;
            
            if (specialization) {
                // If dentist requested, look for 'dental' or 'dentist' in name/types
                candidates = allHospitals.filter(h => 
                    h.name.toLowerCase().includes(specialization) || 
                    (h.types && h.types.includes(specialization)) ||
                    (specialization === 'dentist' && h.name.toLowerCase().includes('dental'))
                );
            }

            // Fallback to all if strict filter fails
            if (!candidates.length) candidates = allHospitals;

            // Sorting Priority: Rating Highest (2), Hospital > Clinic (4)
            candidates.sort((a, b) => {
                const ratingA = a.rating || 0;
                const ratingB = b.rating || 0;
                if (ratingA !== ratingB) return ratingB - ratingA; // Highest rating first
                
                const isHospA = a.types?.includes('hospital') ? 1 : 0;
                const isHospB = b.types?.includes('hospital') ? 1 : 0;
                return isHospB - isHospA; // Hospital > Clinic
            });

            bestMatch = candidates[0];
        }

        if (bestMatch) {
            // Zoom to marker, open popup, book
            setSelectedHospital(bestMatch);
            map.panTo(bestMatch.geometry.location);
            map.setZoom(16);
        } else {
            alert("Could not find a suitable hospital match.");
        }
    };

    const toggleVoice = () => {
        if (!recognitionRef.current) return alert("Browser does not support Speech API.");
        if (isListening) recognitionRef.current.stop();
        else {
            setIsListening(true);
            recognitionRef.current.start();
        }
    };

    // FEATURE 8 - BOOKING SYSTEM
    const bookAppointment = (hospital) => {
        const appointment = {
            appointment_id: "APT" + Math.floor(Math.random() * 100000),
            hospital_name: hospital.name,
            district: districtName || 'Unknown',
            date: new Date().toISOString().split('T')[0],
            time: new Date().toLocaleTimeString(),
            status: "Confirmed"
        };

        setAppointments([...appointments, appointment]);
        alert(`Booking Confirmed!\nID: ${appointment.appointment_id}\nHospital: ${appointment.hospital_name}\nStatus: ${appointment.status}`);
    };

    if (loadError) return <div>Error loading maps</div>;
    if (!isLoaded) return <div>Loading Google Maps...</div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'sans-serif' }}>

            <header style={{ padding: '16px', background: '#fff', borderBottom: '1px solid #ccc', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <h1 style={{ margin: 0, color: '#b91c1c', fontSize: '1.25rem' }}>GeoVoice SmartClinic (Places API)</h1>

                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <select 
                        value={stateName} 
                        onChange={(e) => setStateName(e.target.value)} 
                        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
                    >
                        <option value="">-- Select State --</option>
                        {INDIA_STATES.map(st => <option key={st} value={st}>{st}</option>)}
                    </select>

                    <input 
                        type="text" 
                        placeholder="Enter Any District..." 
                        value={districtName} 
                        onChange={(e) => setDistrictName(e.target.value)} 
                        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc', minWidth: '200px' }}
                        onKeyDown={(e) => e.key === 'Enter' && handleManualSearch()}
                    />

                    <button 
                        onClick={handleManualSearch}
                        style={{ padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                    >
                        Search
                    </button>

                    <div style={{ width: '1px', height: '30px', background: '#ccc', margin: '0 5px' }}></div>

                    <button 
                        onClick={toggleVoice} 
                        style={{ padding: '8px 16px', backgroundColor: isListening ? '#ef4444' : '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}
                    >
                        🎙️ {isListening ? 'Listening...' : 'Voice Command'}
                    </button>
                </div>
            </header>

            <main style={{ flex: 1, position: 'relative' }}>
                <GoogleMap
                    mapContainerStyle={mapContainerStyle}
                    center={defaultCenter}
                    zoom={5}
                    onLoad={onLoad}
                    onUnmount={onUnmount}
                >
                    {/* FEATURE 3 - SHOW ALL MARKERS SAME COLOR (Red Dot) */}
                    {hospitals.map((place, idx) => (
                        <Marker
                            key={`${place.place_id}-${idx}`}
                            position={place.geometry.location}
                            icon={"http://maps.google.com/mapfiles/ms/icons/red-dot.png"}
                            onClick={() => {
                                setSelectedHospital(place);
                                map.panTo(place.geometry.location);
                                map.setZoom(16);
                            }}
                        />
                    ))}

                    {/* FEATURE 9 - MAP POPUP */}
                    {selectedHospital && (
                        <InfoWindow
                            position={selectedHospital.geometry.location}
                            onCloseClick={() => setSelectedHospital(null)}
                        >
                            <div style={{ padding: '5px', maxWidth: '250px' }}>
                                <h3 style={{ margin: '0 0 5px 0', fontSize: '15px' }}>{selectedHospital.name}</h3>
                                <p style={{ margin: '0 0 5px 0', fontSize: '13px', color: '#4b5563' }}>
                                    📍 {selectedHospital.vicinity || selectedHospital.formatted_address}
                                </p>
                                {selectedHospital.rating && (
                                    <p style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#b45309', fontWeight: 'bold' }}>
                                        ⭐ Rating: {selectedHospital.rating} / 5.0
                                    </p>
                                )}
                                <button
                                    onClick={() => bookAppointment(selectedHospital)}
                                    style={{ width: '100%', padding: '8px', backgroundColor: '#dc2626', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                                >
                                    Book Now
                                </button>
                            </div>
                        </InfoWindow>
                    )}
                </GoogleMap>
            </main>
        </div>
    );
}
