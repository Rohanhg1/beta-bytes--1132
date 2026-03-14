import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import './index.css';

// Fix for default Leaflet marker icons in React
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    tooltipAnchor: [16, -28],
    shadowSize: [41, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom Marker component
const HospitalMarker = ({ data }) => {
    return (
        <Marker position={[data.lat, data.lng]}>
            <Popup>
                <div className="p-2 min-w-48">
                    <h3 className="text-lg font-bold text-blue-800">{data.name}</h3>
                    <p className="text-sm font-semibold text-purple-600 mt-1">🩺 {data.specialization}</p>
                    <p className="text-sm text-yellow-600 mt-1">⭐ Rating: {data.rating}/5.0</p>
                    <button
                        className="mt-3 w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition"
                        onClick={() => alert(`Booking appointment at ${data.name} for ${data.specialization}...`)}
                    >
                        Voice Book This Hospital
                    </button>
                </div>
            </Popup>
        </Marker>
    );
};

// Component to handle map view updates natively within Leaflet context
const MapController = ({ center }) => {
    const map = useMap();
    useEffect(() => {
        if (center && center.length === 2 && center[0] !== 0) {
            map.flyTo(center, 12, { animate: true, duration: 1.5 });
        }
    }, [center, map]);
    return null;
};

const App = () => {
    const [hospitals, setHospitals] = useState([]);
    
    // Dynamic Location State
    const [statesList, setStatesList] = useState([]);
    const [districtsList, setDistrictsList] = useState([]);
    
    const [state, setState] = useState('');
    const [district, setDistrict] = useState('');
    const [mapCenter, setMapCenter] = useState([20.5937, 78.9629]); // Default India

    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef(null);
    
    // Result Panel State
    const [bookingResult, setBookingResult] = useState(null);

    // Fetch States on Mount
    useEffect(() => {
        axios.get('http://localhost:8000/api/states')
            .then(res => setStatesList(res.data))
            .catch(err => console.error("Error fetching states:", err));
    }, []);

    // Fetch Districts when State changes
    useEffect(() => {
        if (!state) {
            setDistrictsList([]);
            return;
        }
        const stateObj = statesList.find(s => s.state_name === state);
        if (stateObj) {
            axios.get(`http://localhost:8000/api/states/${stateObj.state_id}/districts`)
                .then(res => setDistrictsList(res.data))
                .catch(err => console.error(err));
        } else {
             // Fallback to fetch all districts and filter
             axios.get('http://localhost:8000/api/districts')
                .then(res => setDistrictsList(res.data))
                .catch(err => console.error(err));
        }
    }, [state, statesList]);

    // Fetch Hospitals when District changes
    const fetchHospitals = async (selectedState, selectedDistrict) => {
        try {
            let url = `http://localhost:8000/hospitals?`;
            if (selectedState) url += `state=${selectedState}&`;
            if (selectedDistrict) url += `district=${selectedDistrict}`;

            const response = await axios.get(url);
            const data = response.data;
            setHospitals(data);

            if (data.length > 0) {
                // Find best rated hospital to center map
                const bestMatched = data.sort((a, b) => b.rating - a.rating)[0];
                setMapCenter([bestMatched.lat, bestMatched.lng]);
            }
        } catch (error) {
            console.error("Error fetching hospitals:", error);
        }
    };

    useEffect(() => {
        if (district) {
            fetchHospitals(state, district);
        }
    }, [district, state]);

    // Voice Search Setup
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.lang = 'en-IN';
            recognitionRef.current.continuous = false;

            recognitionRef.current.onresult = async (event) => {
                const transcript = event.results[0][0].transcript;
                handleVoiceCommand(transcript);
                setIsListening(false);
            };

            recognitionRef.current.onerror = () => setIsListening(false);
            recognitionRef.current.onend = () => setIsListening(false);
        }
    }, [district, state]);

    const handleVoiceCommand = async (text) => {
        try {
            const payload = {
                text: text,
                district: district,
                state: state
            };
            
            // Note: In production we use /api/voice/book
            const resp = await axios.post('http://localhost:8000/api/voice/book', payload);
            const data = resp.data;
            
            if (data.success && data.matched_hospital) {
                const foundDist = data.intent?.district || district;
                const foundState = data.intent?.state || state;
                
                // Show Result Panel
                setBookingResult({
                    nodes: data.found_nodes || 1,
                    rating: data.matched_hospital.rating || 4.5,
                    hospital: data.matched_hospital.hospital_name,
                    district: foundDist,
                    specialization: data.intent?.specialization || 'General',
                    token: data.appointment ? data.appointment.appointment_id + 1000 : 1025,
                    date: data.appointment?.date || 'Today',
                    time: data.appointment?.time || '10:00 AM'
                });
                
                // Read confirmation out loud
                const synth = window.speechSynthesis;
                if (synth) {
                    const utterance = new SpeechSynthesisUtterance(data.message);
                    synth.speak(utterance);
                }
                
                // Update map UI
                if (foundDist && foundDist !== district) {
                    setDistrict(foundDist);
                    if (foundState) setState(foundState);
                    fetchHospitals(foundState, foundDist);
                }
                
                setMapCenter([data.matched_hospital.latitude, data.matched_hospital.longitude]);
                
            } else {
                alert(data.message || "Could not understand your booking request.");
            }
        } catch (e) { 
            console.error(e);
            alert("Error processing voice request. Please check backend is running.");
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

    return (
        <div className="flex flex-col h-screen bg-gray-50 font-sans">
            <header className="bg-white shadow p-4 flex justify-between items-center z-20 relative">
                <h1 className="text-2xl font-bold text-blue-900">🗺️ SmartClinic Manager</h1>

                <div className="flex gap-4">
                    <select
                        className="border p-2 rounded outline-none focus:ring-2 ring-blue-500"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                    >
                        <option value="">-- All States --</option>
                        {statesList.map(s => (
                            <option key={s.state_id} value={s.state_name}>{s.state_name}</option>
                        ))}
                    </select>

                    <select
                        className="border p-2 rounded outline-none focus:ring-2 ring-blue-500"
                        value={district}
                        onChange={(e) => setDistrict(e.target.value)}
                        disabled={!state}
                    >
                        <option value="">-- All Districts --</option>
                        {districtsList.map(d => (
                            <option key={d.district_id} value={d.district_name}>{d.district_name}</option>
                        ))}
                    </select>

                    <button
                        className={`flex items-center gap-2 px-4 py-2 rounded text-white font-semibold transition ${isListening ? 'bg-red-500 animate-pulse' : 'bg-green-600 hover:bg-green-700'}`}
                        onClick={toggleVoice}
                        title="Say 'Book Apollo Hospital' or 'I need a cardiologist in Mumbai'"
                    >
                        🎙️ {isListening ? 'Listening...' : 'Voice Search'}
                    </button>
                </div>
            </header>

            <main className="flex-grow relative z-0">
                <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        attribution='&copy; OpenStreetMap contributors'
                        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                    />
                    <MapController center={mapCenter} />

                    {hospitals.map((h, i) => (
                        <HospitalMarker key={h.hospital_id || i} data={h} />
                    ))}
                </MapContainer>
                
                {/* Floating Result Panel UI */}
                {bookingResult && (
                    <div className="absolute top-4 left-4 z-[1000] bg-white bg-opacity-95 p-6 rounded-lg shadow-xl border border-blue-200 min-w-80 backdrop-blur-sm">
                        <h2 className="text-xl font-extrabold text-blue-900 mb-4 border-b pb-2">HOSPITAL MATCHES</h2>
                        <ul className="space-y-3 font-medium text-gray-700">
                            <li className="flex justify-between">
                                <span>Found Nodes:</span>
                                <span className="font-bold text-blue-700">{bookingResult.nodes}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Max Rating:</span>
                                <span className="font-bold text-yellow-600">⭐ {bookingResult.rating}</span>
                            </li>
                            <li className="flex justify-between mt-4 pt-2 border-t">
                                <span>Booked Hospital:</span>
                                <span className="font-bold text-green-700 text-right max-w-[150px] truncate">{bookingResult.hospital}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>District:</span>
                                <span className="font-bold">{bookingResult.district}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Specialist:</span>
                                <span className="font-bold text-purple-700">{bookingResult.specialization}</span>
                            </li>
                            <li className="flex justify-between mt-4 pt-2 border-t">
                                <span>Token Number:</span>
                                <span className="font-bold text-white bg-green-700 px-2 py-0.5 rounded">{bookingResult.token}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Schedule:</span>
                                <span className="font-bold text-gray-800 text-right max-w-[150px] truncate">{bookingResult.date} at {bookingResult.time}</span>
                            </li>
                        </ul>
                        <button 
                            className="w-full mt-6 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 rounded transition"
                            onClick={() => setBookingResult(null)}
                        >
                            Close Panel
                        </button>
                    </div>
                )}
            </main>
        </div>
    );
};

export default App;
