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
    const [district, setDistrict] = useState('');
    const [state, setState] = useState('');
    const [mapCenter, setMapCenter] = useState([20.5937, 78.9629]); // Default India

    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef(null);

    // FEATURE 5 - AUTO LOAD ON DISTRICT SELECT
    const fetchHospitals = async (selectedState, selectedDistrict) => {
        try {
            let url = `http://localhost:8000/hospitals?`;
            if (selectedState) url += `state=${selectedState}&`;
            if (selectedDistrict) url += `district=${selectedDistrict}`;

            const response = await axios.get(url);
            const data = response.data;
            setHospitals(data);

            if (data.length > 0) {
                // Find best rated hospital or just the first to center map
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
    }, []);

    const handleVoiceCommand = async (text) => {
        const lowerText = text.toLowerCase();

        // FEATURE 6: Extract district/specialization logically
        // (In production, you route this through FastAPI intent extractor)
        const knownSpecAliases = {
            dentist: "Dentist", dental: "Dentist",
            cardiologist: "Cardiologist", heart: "Cardiologist",
            skin: "Dermatologist", dermatologist: "Dermatologist"
        };

        let spec = "";
        Object.keys(knownSpecAliases).forEach(k => {
            if (lowerText.includes(k)) spec = knownSpecAliases[k];
        });

        // We expect user to say "I need dentist in Mysore"
        let voiceDist = district; // fallback to selected
        if (lowerText.includes("mysore")) voiceDist = "Mysore";
        if (lowerText.includes("bangalore") || lowerText.includes("bengaluru")) voiceDist = "Bangalore Urban";

        // API Call
        let url = `http://localhost:8000/hospitals?district=${voiceDist}`;
        if (spec) url += `&specialization=${spec}`;

        // FEATURE 7: Specific Hospital Voice Logic
        if (lowerText.includes("book")) {
            alert(`Auto-analyzing custom booking intent from: "${text}"`);
            // Further extraction logic
            return;
        }

        try {
            const resp = await axios.get(url);
            setHospitals(resp.data);
            if (resp.data.length > 0) {
                setDistrict(voiceDist); // Sync UI
                const target = resp.data[0];
                setMapCenter([target.lat, target.lng]); // Highlight best
            } else {
                alert("No matching hospitals found for your voice request.");
            }
        } catch (e) { console.error(e); }
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
            <header className="bg-white shadow p-4 flex justify-between items-center z-10 relative">
                <h1 className="text-2xl font-bold text-blue-900">🗺️ GeoVoice Clinic Map</h1>

                <div className="flex gap-4">
                    <select
                        className="border p-2 rounded outline-none focus:ring-2 ring-blue-500"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                    >
                        <option value="">-- All States --</option>
                        <option value="Karnataka">Karnataka</option>
                        <option value="Maharashtra">Maharashtra</option>
                    </select>

                    <select
                        className="border p-2 rounded outline-none focus:ring-2 ring-blue-500"
                        value={district}
                        onChange={(e) => setDistrict(e.target.value)}
                    >
                        <option value="">-- All Districts --</option>
                        <option value="Mysore">Mysore</option>
                        <option value="Bangalore Urban">Bangalore</option>
                        <option value="Mumbai Suburban">Mumbai</option>
                    </select>

                    <button
                        className={`flex items-center gap-2 px-4 py-2 rounded text-white font-semibold transition ${isListening ? 'bg-red-500 animate-pulse' : 'bg-green-600 hover:bg-green-700'}`}
                        onClick={toggleVoice}
                    >
                        🎙️ {isListening ? 'Listening...' : 'Voice Search'}
                    </button>
                </div>
            </header>

            {/* FEATURE 3 - FRONTEND MAP */}
            <main className="flex-grow relative z-0">
                <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        attribution='&copy; OpenStreetMap contributors'
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                    />
                    <MapController center={mapCenter} />

                    {/* FEATURE 4 - ADD MARKERS */}
                    {hospitals.map((h, i) => (
                        <HospitalMarker key={h.hospital_id || i} data={h} />
                    ))}
                </MapContainer>
            </main>
        </div>
    );
};

export default App;
