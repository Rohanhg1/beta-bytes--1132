/* ============================================================
   SmartClinic GeoVoice - Frontend JavaScript
   Integration with Leaflet Maps, Web Speech API, and FastAPI
   ============================================================ */

const API_BASE = window.location.origin + '/api';

// ============ STATE ============
let authToken = localStorage.getItem('smartclinic_token');
let currentUser = null;
let isListening = false;
let recognition = null;
let map = null;
let markerCluster = null;   // Leaflet.markercluster group
let mapMarkers = [];

let statesData = [];
let districtsData = [];
let currentSelectedState = null;
let currentSelectedDistrict = null;

let selectedTimeSlot = null;
let currentLang = 'kn-IN';  // active voice language

function selectTimeSlot(slot) {
    selectedTimeSlot = slot;
    document.getElementById('selected-time-slot').value = slot;
    const btns = document.querySelectorAll('.time-slot-btn');
    btns.forEach(btn => {
        if (btn.textContent === slot) {
            btn.style.background = '#4f46e5';
            btn.style.color = '#fff';
            btn.style.borderColor = '#4f46e5';
            btn.style.boxShadow = '0 4px 12px rgba(79, 70, 229, 0.3)';
        } else {
            btn.style.background = 'transparent';
            btn.style.color = '#4f46e5';
            btn.style.boxShadow = 'none';
        }
    });
}


// ============ INITIALIZATION ============
document.addEventListener('DOMContentLoaded', () => {
    initSpeechRecognition();
    setVoiceLanguage(currentLang); // Ensure UI matches the default language
    initMap();
    loadStates();
    loadAllHospitals();
    checkAuth();
    updateNavForAuth();
});

// ============ NAVIGATION ============
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    const page = document.getElementById(pageId);
    if (page) page.classList.add('active');

    document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
    const navLink = document.getElementById('nav-' + pageId.replace('-page', ''));
    if (navLink) navLink.classList.add('active');

    if (pageId === 'dashboard') loadDashboard();
    if (pageId === 'hospitals-page') loadAllHospitals();

    // Resize map if booking page shown (Leaflet glitch fix)
    if (pageId === 'booking' && map) {
        setTimeout(() => { map.invalidateSize(); }, 200);
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleMobileMenu() {
    document.getElementById('mobile-menu').classList.toggle('open');
}

function updateNavForAuth() {
    const loginLink = document.getElementById('nav-login');
    if (authToken && currentUser) {
        loginLink.textContent = 'Admin Portal';
        loginLink.onclick = (e) => { e.preventDefault(); showPage('dashboard'); };
    } else {
        loginLink.textContent = 'Admin Portal';
        loginLink.onclick = (e) => { e.preventDefault(); showPage('login'); };
    }
}

// ============ MAP & GEO DATA ============
function initMap() {
    // Zoom to a default area instead of full India
    map = L.map('hospital-map').setView([13.9299, 75.5681], 10); // Default to Shivamogga region
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &amp; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);
}

async function loadStates() {
    try {
        const res = await fetch(`${API_BASE}/states`);
        statesData = await res.json();

        const stateSelect = document.getElementById('state-select');
        const filterSelect = document.getElementById('hosp-filter-state');

        const optionsHTML = statesData.map(s => {
            return `<option value="${s.state_id}">${s.state_name}</option>`;
        }).join('');

        const selectLabel = currentLang === 'kn-IN' ? 'ರಾಜ್ಯ ಆಯ್ಕೆಮಾಡಿ' : (currentLang === 'hi-IN' ? 'राज्य चुनें' : 'Select State');
        const allStatesLabel = currentLang === 'kn-IN' ? 'ಎಲ್ಲಾ ರಾಜ್ಯಗಳು' : (currentLang === 'hi-IN' ? 'सभी राज्य' : 'All States');

        stateSelect.innerHTML = `<option value="" disabled selected>${selectLabel}</option>` + optionsHTML;
        filterSelect.innerHTML = `<option value="">${allStatesLabel}</option>` + optionsHTML;

        // Also update district placeholder if none selected
        if (!stateSelect.value) {
            const distSelectLabel = currentLang === 'kn-IN' ? 'ಜಿಲ್ಲೆ ಆಯ್ಕೆಮಾಡಿ' : (currentLang === 'hi-IN' ? 'जिला चुनें' : 'Select District');
            document.getElementById('district-select').innerHTML = `<option value="" disabled selected>${distSelectLabel}</option>`;
        }
    } catch (e) {
        console.error("Failed to load states", e);
    }
}

async function onStateChange() {
    const stateId = document.getElementById('state-select').value;
    const districtSelect = document.getElementById('district-select');

    currentSelectedState = statesData.find(s => s.state_id == stateId)?.state_name;

    try {
        const res = await fetch(`${API_BASE}/states/${stateId}/districts`);
        districtsData = await res.json();

        const distSelectLabel = currentLang === 'kn-IN' ? 'ಜಿಲ್ಲೆ ಆಯ್ಕೆಮಾಡಿ' : (currentLang === 'hi-IN' ? 'जिला चुनें' : 'Select District');
        districtSelect.innerHTML = `<option value="" disabled selected>${distSelectLabel}</option>` +
            districtsData.map(d => {
                return `<option value="${d.district_id}">${d.district_name}</option>`;
            }).join('');

        districtSelect.disabled = false;

        // Zoom to state level — use average of district coords
        const validDistricts = districtsData.filter(d => d.latitude && d.longitude);
        if (validDistricts.length > 0) {
            const avgLat = validDistricts.reduce((s, d) => s + d.latitude, 0) / validDistricts.length;
            const avgLng = validDistricts.reduce((s, d) => s + d.longitude, 0) / validDistricts.length;
            map.setView([avgLat, avgLng], 8, { animate: true });
        }

    } catch (e) {
        console.error("Failed to load districts", e);
    }
}

async function onDistrictChange() {
    const districtId = document.getElementById('district-select').value;
    const distData = districtsData.find(d => d.district_id == districtId);

    if (distData) {
        currentSelectedDistrict = distData.district_name;

        // Immediately zoom into district before hospitals load
        if (distData.latitude && distData.longitude) {
            map.setView([distData.latitude, distData.longitude], 11, { animate: true });
        }

        setVoiceStatus('⏳ Loading hospitals & clinics...', true);

        // Store district coords for use by fetchAndMapHospitals
        window._districtLat = distData.latitude;
        window._districtLng = distData.longitude;

        // Show hospitals in this district (pass state for better dynamic fetching)
        await fetchAndMapHospitals(distData.district_name, null, currentSelectedState);

        setVoiceStatus('Click mic and say "I need a doctor" or a disease', false);
    }
}

function clearMapMarkers() {
    mapMarkers.forEach(m => map.removeLayer(m));
    mapMarkers = [];
}

async function fetchAndMapHospitals(districtName, topHospitalId = null, stateName = null) {
    try {
        let url = `${API_BASE}/hospitals?district_name=${encodeURIComponent(districtName)}`;
        if (stateName) url += `&state_name=${encodeURIComponent(stateName)}`;

        const res = await fetch(url);
        let hospitals = await res.json();

        clearMapMarkers();

        const distLat = window._districtLat;
        const distLng = window._districtLng;

        const isDistrictMatch = (hName, searchName) => {
            if (!hName || !searchName) return true;
            const h = hName.toLowerCase();
            const s = searchName.toLowerCase();
            if (h === s) return true;
            // Aliases
            const m = ["mangalore", "mangaluru", "manglor"];
            if (m.includes(h) && m.includes(s)) return true;
            const u = ["udupi", "udapi", "uduppi"];
            if (u.includes(h) && u.includes(s)) return true;
            const b = ["bangalore", "bengaluru", "bangaluru", "bangalor", "bangalore urban"];
            if (b.some(x => h.includes(x)) && b.some(x => s.includes(x))) return true;
            return h.includes(s) || s.includes(h);
        };

        // Filter 1: Relaxed district name match
        if (districtName) {
            hospitals = hospitals.filter(h =>
                h.district_name && isDistrictMatch(h.district_name, districtName)
            );
        }

        // Filter 2: Coordinate bounding box (~55km) to remove OSM entries with wrong coords
        if (distLat && distLng) {
            hospitals = hospitals.filter(h => {
                if (!h.latitude || !h.longitude) return false;
                return Math.abs(h.latitude - distLat) < 0.5 && Math.abs(h.longitude - distLng) < 0.5;
            });
        }

        // Sort by rating, cap at 100 to prevent visual overload
        hospitals.sort((a, b) => (b.rating || 0) - (a.rating || 0));
        hospitals = hospitals.slice(0, 100);

        // Update stat panels
        window.currentHospitalsCount = hospitals.length;
        const panelNodes = document.getElementById('panel-found-nodes');
        if (panelNodes) panelNodes.textContent = hospitals.length;
        const countBadge = document.getElementById('map-hospital-count');
        if (countBadge) countBadge.textContent = `🏥 ${hospitals.length} Hospitals & Clinics Found`;

        let topMarkerToOpen = null;

        hospitals.forEach(h => {
            const isTop = h.hospital_id === topHospitalId;
            const color  = isTop ? '#7c3aed' : '#dc2626';
            const size   = isTop ? '2.5rem' : '1.2rem';

            const customIcon = L.divIcon({
                className: 'custom-pin',
                iconAnchor: [0, 24],
                html: `<span style="background-color:${color};width:${size};height:${size};display:block;
                        left:-0.6rem;top:-0.6rem;position:relative;border-radius:3rem 3rem 0;
                        transform:rotate(45deg);border:2px solid #FFF;
                        box-shadow:0 3px 6px rgba(0,0,0,0.35);"></span>`
            });

            const marker = L.marker([h.latitude, h.longitude], { icon: customIcon }).addTo(map);
            marker.bindPopup(`
                <div style="min-width:180px;">
                    <h3 style="margin:0 0 6px;font-size:14px;">🏥 ${h.hospital_name}</h3>
                    <p style="margin:2px 0;"><strong><span class="rate-badge">⭐ ${h.rating || '4.0'}</span></strong></p>
                    <p style="margin:4px 0;font-size:12px;"><strong>Specialists:</strong><br>
                       ${h.specializations.split(',').slice(0, 3).join(', ')}</p>
                    <p style="margin:4px 0;font-size:11px;color:#666;">📍 ${h.district_name}</p>
                </div>
            `);
            mapMarkers.push(marker);
            if (isTop) topMarkerToOpen = marker;
        });

        // Center map to maintain the district view. If a specific hospital was booked, center exactly on that hospital at district level.
        if (topMarkerToOpen) {
            map.setView(topMarkerToOpen.getLatLng(), 11, { animate: true });
            // Delay the popup slightly to ensure map pan completes smoothly
            setTimeout(() => { topMarkerToOpen.openPopup(); }, 400);
        } else if (distLat && distLng) {
            map.setView([distLat, distLng], 11, { animate: true });
        }

    } catch (e) {
        console.error('Failed to map hospitals', e);
        setVoiceStatus('Failed to load hospitals. Please try again.', false);
    }
}


// ============ NATIVE NAME MAPS ============
const NATIVE_STATE_NAMES = {
    'kn-IN': { 'Karnataka': 'ಕರ್ನಾಟಕ', 'Maharashtra': 'ಮಹಾರಾಷ್ಟ್ರ', 'Tamil Nadu': 'ತಮಿಳುನಾಡು', 'Kerala': 'ಕೇರಳ' },
    'hi-IN': { 'Karnataka': 'कर्नाटक', 'Maharashtra': 'महाराष्ट्र', 'Tamil Nadu': 'तमिलनाडु', 'Kerala': 'केरल', 'Uttar Pradesh': 'उत्तर प्रदेश' }
};

const NATIVE_DISTRICT_NAMES = {
    'kn-IN': {
        'Mangalore': 'ಮಂಗಳೂರು', 'Udupi': 'ಉಡುಪಿ', 'Shivamogga': 'ಶಿವಮೊಗ್ಗ', 'Bangalore Urban': 'ಬೆಂಗಳೂರು',
        'Mysore': 'ಮೈಸೂರು', 'Tumkur': 'ತುಮಕೂರು', 'Kolar': 'ಕೋಲಾರ', 'Hassan': 'ಹಾಸನ', 'Belgaum': 'ಬೆಳಗಾವಿ'
    },
    'hi-IN': {
        'Mangalore': 'मंगलुरु', 'Udupi': 'उडुपी', 'Shivamogga': 'शिमोगा', 'Bangalore Urban': 'बेंगलुरु',
        'Mysore': 'मैसूर', 'Shimoga': 'शिमोगा'
    }
};

function getLocalizedName(englishName, type = 'state') {
    const map = type === 'state' ? NATIVE_STATE_NAMES[currentLang] : NATIVE_DISTRICT_NAMES[currentLang];
    return (map && map[englishName]) ? map[englishName] : englishName;
}

// ============ MULTILINGUAL UI TRANSLATIONS ============
const UI_TRANSLATIONS = {
    'en-IN': {
        NAV_HOME: 'Home',
        NAV_BOOKING: 'Book Hospital',
        NAV_ALL_HOSPITALS: 'All Hospitals',
        NAV_ADMIN: 'Admin Portal',
        HERO_TITLE: 'Voice + Map Powered<br><span class="gradient-text">Hospital Booking</span>',
        HERO_SUBTITLE: 'Select your state and district in India, speak your disease or hospital name, and let our AI find the absolute best hospital and book it instantly.',
        BTN_START_VOICE: 'Start Voice Booking',
        BTN_EXPLORE_MAP: 'Explore Map',
        MAP_TITLE: '📍 India Location Map',
        MAP_SUBTITLE: 'Select location to discover hospitals',
        VOICE_TITLE: '🎙️ Voice Receptionist',
        VOICE_SUBTITLE: 'Speak disease, specialization or hospital name',
        LABEL_TIME_SLOT: 'Select Appt Time (Required)',
        OR_TYPE: 'or type request',
        BTN_SEND: 'Send',
        LABEL_STATE: 'State',
        LABEL_DISTRICT: 'District',
        PLACEHOLDER_MANUAL: 'e.g. Book Apollo Hospital in Bangalore',
        STEP1_TITLE: '1. Select Location',
        STEP1_DESC: 'Pick your State and District. Our Leaflet map will automatically zero in on your selected area in India.',
        STEP2_TITLE: '2. Speak Your Need',
        STEP2_DESC: 'Say "I have chest pain" or "Book Apollo Hospital". Whisper API instantly converts speech to text.',
        STEP3_TITLE: '3. AI Matching',
        STEP3_DESC: 'Our deep matching engine links your disease to a specialty and finds the best rated hospital.',
        STEP4_TITLE: '4. Instant Booking & TTS',
        STEP4_DESC: 'We trigger an AI Voice Confirmation and SMTP Email, booking you into the local hospital automatically.',
        PANEL_RESULTS_TITLE: 'HOSPITAL MATCHES',
        PANEL_NODES: 'Found Nodes',
        PANEL_MAX_RATING: 'Max Rating',
        PANEL_LOCATION: 'LOCATION',
        PANEL_SPECIALTY: 'SPECIALTY',
        PANEL_TOKEN: 'Token Number',
        TIME_MORNING: '9:00 AM – 11:00 AM',
        TIME_AFTERNOON: '11:00 AM – 1:00 PM',
        TIME_EVENING: '2:00 PM – 3:00 PM',
        TIME_NIGHT: '3:00 PM – 6:00 PM',
        TRY_SAYING: 'Try saying:',
        HINT_1: '"I have severe chest pain"',
        HINT_2: '"Book Apollo Hospital for 6 PM"',
        HINT_3: '"I need a skin doctor"',
    },
    'kn-IN': {
        NAV_HOME: 'ಮುಖಪುಟ',
        NAV_BOOKING: 'ಆಸ್ಪತ್ರೆ ಬುಕಿಂಗ್',
        NAV_ALL_HOSPITALS: 'ಎಲ್ಲಾ ಆಸ್ಪತ್ರೆಗಳು',
        NAV_ADMIN: 'ನಿರ್ವಾಹಕರು',
        HERO_TITLE: 'ಧ್ವನಿ + ನಕ್ಷೆ ಆಧಾರಿತ<br><span class="gradient-text">ಆಸ್ಪತ್ರೆ ಬುಕಿಂಗ್</span>',
        HERO_SUBTITLE: 'ನಿಮ್ಮ ರಾಜ್ಯ ಮತ್ತು ಜಿಲ್ಲೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ, ನಿಮ್ಮ ಕಾಯಿಲೆ ಅಥವಾ ಆಸ್ಪತ್ರೆಯ ಹೆಸರನ್ನು ಹೇಳಿ, ಮತ್ತು ನಮ್ಮ AI ಅತ್ಯುತ್ತಮ ಆಸ್ಪತ್ರೆಯನ್ನು ತಕ್ಷಣವೇ ಕಾಯ್ದಿರಿಸಲು ಬಿಡಿ.',
        BTN_START_VOICE: 'ಧ್ವನಿ ಬುಕಿಂಗ್ ಪ್ರಾರಂಭಿಸಿ',
        BTN_EXPLORE_MAP: 'ನಕ್ಷೆಯನ್ನು ಅನ್ವೇಷಿಸಿ',
        MAP_TITLE: '📍 ಭಾರತ ಸ್ಥಳ ನಕ್ಷೆ',
        MAP_SUBTITLE: 'ಆಸ್ಪತ್ರೆಗಳನ್ನು ಕಂಡುಹಿಡಿಯಲು ಸ್ಥಳವನ್ನು ಆಯ್ಕೆಮಾಡಿ',
        VOICE_TITLE: '🎙️ ಧ್ವನಿ ಸ್ವಾಗತದ ಅಧಿಕಾರಿ',
        VOICE_SUBTITLE: 'ಕಾಯಿಲೆ, ಪರಿಣಿತಿ ಅಥವಾ ಆಸ್ಪತ್ರೆ ಹೆಸರು ಹೇಳಿ',
        LABEL_TIME_SLOT: 'ಸಮಯವನ್ನು ಆಯ್ಕೆಮಾಡಿ (ಅಗತ್ಯವಿದೆ)',
        OR_TYPE: 'ಅಥವಾ ಟೈಪ್ ಮಾಡಿ',
        BTN_SEND: 'ಕಳುಹಿಸಿ',
        LABEL_STATE: 'ರಾಜ್ಯ',
        LABEL_DISTRICT: 'ಜಿಲ್ಲೆ',
        PLACEHOLDER_MANUAL: 'ಉದಾ: ಬೆಂಗಳೂರಿನಲ್ಲಿ ಅಪೊಲೊ ಆಸ್ಪತ್ರೆ',
        STEP1_TITLE: '1. ಸ್ಥಳವನ್ನು ಆಯ್ಕೆಮಾಡಿ',
        STEP1_DESC: 'ನಿಮ್ಮ ರಾಜ್ಯ ಮತ್ತು ಜಿಲ್ಲೆಯನ್ನು ಆರಿಸಿ. ನಮ್ಮ ಮ್ಯಾಪ್ ಭಾರತದಲ್ಲಿ ನಿಮ್ಮ ಪ್ರದೇಶವನ್ನು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಪತ್ತೆ ಮಾಡುತ್ತದೆ.',
        STEP2_TITLE: '2. ನಿಮ್ಮ ಅಗತ್ಯವನ್ನು ಹೇಳಿ',
        STEP2_DESC: '"ನನಗೆ ಎದೆ ನೋವು ಇದೆ" ಅಥವಾ "ಅಪೊಲೊ ಆಸ್ಪತ್ರೆ ಬುಕ್ ಮಾಡಿ" ಎಂದು ಹೇಳಿ. ನಮ್ಮ AI ತಕ್ಷಣವೇ ಅದನ್ನು ಪತ್ತೆಹಚ್ಚುತ್ತದೆ.',
        STEP3_TITLE: '3. AI ಹೊಂದಾಣಿಕೆ',
        STEP3_DESC: 'ನಮ್ಮ ಎಂಜಿನ್ ನಿಮ್ಮ ಕಾಯಿಲೆಯನ್ನು ಸರಿಯಾದ ತಜ್ಞ ವೈದ್ಯರಿಗೆ ಮತ್ತು ಉತ್ತಮ ಆಸ್ಪತ್ರೆಗೆ ಲಿಂಕ್ ಮಾಡುತ್ತದೆ.',
        STEP4_TITLE: '4. ತ್ವರಿತ ಬುಕಿಂಗ್',
        STEP4_DESC: 'ನಾವು ಧ್ವನಿ ದೃಢೀಕರಣ ಮತ್ತು ಇಮೇಲ್ ಮೂಲಕ ಆಸ್ಪತ್ರೆಯನ್ನು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಬುಕ್ ಮಾಡುತ್ತೇವೆ.',
        PANEL_RESULTS_TITLE: 'ಆಸ್ಪತ್ರೆ ಫಲಿತಾಂಶಗಳು',
        PANEL_NODES: 'ಸಿಕ್ಕಿರುವ ಆಸ್ಪತ್ರೆಗಳು',
        PANEL_MAX_RATING: 'ಗರಿಷ್ಠ ರೇಟಿಂಗ್',
        PANEL_LOCATION: 'ಸ್ಥಳ',
        PANEL_SPECIALTY: 'ವಿಭಾಗ',
        PANEL_TOKEN: 'ಟೋಕನ್ ಸಂಖ್ಯೆ',
        TIME_MORNING: 'ಬೆಳಿಗ್ಗೆ 9:00 - 11:00',
        TIME_AFTERNOON: 'ಮಧ್ಯಾಹ್ನ 11:00 - 1:00',
        TIME_EVENING: 'ಸಂಜೆ 2:00 - 3:00',
        TIME_NIGHT: 'ಸಂಜೆ 3:00 - 6:00',
        TRY_SAYING: 'ಹೀಗೆ ಹೇಳಿ:',
        HINT_1: '"ನನಗೆ ಎದೆ ನೋವು ಇದೆ"',
        HINT_2: '"ಅಪೊಲೊ ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ಬುಕ್ ಮಾಡಿ"',
        HINT_3: '"ನನಗೆ ಚರ್ಮದ ವೈದ್ಯರು ಬೇಕು"',
    },
    'hi-IN': {
        NAV_HOME: 'होम',
        NAV_BOOKING: 'अस्पताल बुकिंग',
        NAV_ALL_HOSPITALS: 'सभी अस्पताल',
        NAV_ADMIN: 'एडमिन पोर्टल',
        HERO_TITLE: 'वॉयस + मैप संचालित<br><span class="gradient-text">अस्पताल बुकिंग</span>',
        HERO_SUBTITLE: 'भारत में अपने राज्य और जिले का चयन करें, अपनी बीमारी या अस्पताल का नाम बोलें, और हमारे AI को सबसे अच्छा अस्पताल खोजने और तुरंत बुक करने दें।',
        BTN_START_VOICE: 'वॉयस बुकिंग शुरू करें',
        BTN_EXPLORE_MAP: 'मैप देखें',
        MAP_TITLE: '📍 भारत स्थान मैप',
        MAP_SUBTITLE: 'अस्पतालों को खोजने के लिए स्थान चुनें',
        VOICE_TITLE: '🎙️ वॉयस रिसेप्शनिस्ट',
        VOICE_SUBTITLE: 'बीमारी, विशेषज्ञता या अस्पताल का नाम बोलें',
        LABEL_TIME_SLOT: 'समय चुनें (अनिवार्य)',
        OR_TYPE: 'या टाइप करें',
        BTN_SEND: 'भेजें',
        LABEL_STATE: 'राज्य',
        LABEL_DISTRICT: 'जिला',
        PLACEHOLDER_MANUAL: 'उदा: बैंगलोर में अपोलो अस्पताल',
        STEP1_TITLE: '1. स्थान चुनें',
        STEP1_DESC: 'अपने राज्य और जिले का चयन करें। हमारा मैप आपके क्षेत्र को स्वचालित रूप से खोज लेगा।',
        STEP2_TITLE: '2. अपनी जरूरत बताएं',
        STEP2_DESC: '"मेरे सीने में दर्द है" या "अपोलो अस्पताल बुक करें" कहें। हमारा AI आपकी बात समझ लेगा।',
        STEP3_TITLE: '3. AI मिलान',
        STEP3_DESC: 'हमारा इंजन आपकी बीमारी को सही विशेषज्ञ और बेहतरीन अस्पताल से जोड़ता है।',
        STEP4_TITLE: '4. तुरंत बुकिंग',
        STEP4_DESC: 'हम वॉयस कन्फर्मेशन और ईमेल के जरिए अस्पताल को तुरंत और स्वचालित रूप से बुक करते हैं।',
        PANEL_RESULTS_TITLE: 'अस्पताल के परिणाम',
        PANEL_NODES: 'मिले अस्पताल',
        PANEL_MAX_RATING: 'अधिकतम रेटिंग',
        PANEL_LOCATION: 'स्थान',
        PANEL_SPECIALTY: 'विशेषज्ञता',
        PANEL_TOKEN: 'टोकन संख्या',
        TIME_MORNING: 'सुबह 9:00 - 11:00',
        TIME_AFTERNOON: 'दोपहर 11:00 - 1:00',
        TIME_EVENING: 'दोपहर 2:00 - 3:00',
        TIME_NIGHT: 'शाम 3:00 - 6:00',
        TRY_SAYING: 'ऐसे कहें:',
        HINT_1: '"मेरे सीने में दर्द है"',
        HINT_2: '"अपोलो अस्पताल में बुक करें"',
        HINT_3: '"मुझे त्वचा विशेषज्ञ चाहिए"',
    }
};

function applyUITranslations(lang) {
    const dict = UI_TRANSLATIONS[lang];
    if (!dict) return;

    // 1. Text content translations
    document.querySelectorAll('[data-translate]').forEach(el => {
        const key = el.getAttribute('data-translate');
        if (dict[key]) {
            // If it contains HTML, use innerHTML
            if (dict[key].includes('<')) {
                el.innerHTML = dict[key];
            } else {
                // If it has children (like icons), keep them
                if (el.children.length > 0 && el.tagName !== 'BUTTON') {
                     // Advanced logic could go here, but for hackathon keep it simple
                     el.innerHTML = dict[key];
                } else if (el.tagName === 'BUTTON' && el.querySelector('.btn-icon')) {
                    // Specific fix for buttons with icons
                    const icon = el.querySelector('.btn-icon').outerHTML;
                    el.innerHTML = icon + ' ' + dict[key];
                } else {
                    el.textContent = dict[key];
                }
            }
        }
    });

    // 2. Attribute-based translations (like placeholder)
    document.querySelectorAll('[data-translate-attr]').forEach(el => {
        const meta = el.getAttribute('data-translate-attr');
        const [attr, key] = meta.split(':');
        if (dict[key]) {
            el.setAttribute(attr, dict[key]);
        }
    });
}

// ============ MULTILINGUAL SUPPORT ============
const LANG_LABELS = {
    'en-IN': {
        clickMic:   'Click mic and say "I need a doctor" or a disease',
        listening:  'Listening... speak clearly',
        gotIt:      'Processing your request...',
        noSpeech:   'No speech detected. Please try again.',
        hearing:    'Hearing: ',
        timeout:    'Mic timed out (3s). Speak sooner after clicking.',
        placeholder:'e.g. Book Apollo Hospital in Bangalore',
        subTitle:   'Speak disease, specialization or hospital name',
    },
    'kn-IN': {
        clickMic:   'ಮೈಕ್ ಕ್ಲಿಕ್ ಮಾಡಿ ಮತ್ತು ನಿಮ್ಮ ಕಾಯಿಲೆ ಹೇಳಿ',
        listening:  'ಆಲಿಸುತ್ತಿದ್ದೇನೆ... ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ',
        gotIt:      'ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತಿದೆ...',
        noSpeech:   'ಮಾತು ಕೇಳಿಸಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
        hearing:    'ಕೇಳಿಸುತ್ತಿದೆ: ',
        timeout:    'ಸಮಯ ಮುಗಿಯಿತು. ಮೈಕ್ ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡಿ ಮತ್ತೆ ಮಾತನಾಡಿ.',
        placeholder:'ಉದಾ: ಶಿವಮೊಗ್ಗದಲ್ಲಿ ಹೃದಯ ವೈದ್ಯರು',
        subTitle:   'ಕಾಯಿಲೆ, ತಜ್ಞ ಅಥವಾ ಆಸ್ಪತ್ರೆ ಹೆಸರು ಹೇಳಿ',
    },
    'hi-IN': {
        clickMic:   'माइक दबाएं और बीमारी बताएं',
        listening:  'सुन रहा हूँ... स्पष्ट बोलें',
        gotIt:      'आपके अनुरोध पर कार्रवाई की जा रही है...',
        noSpeech:   'आवाज़ नहीं आई। फिर कोशिश करें।',
        hearing:    'सुन रहा हूँ: ',
        timeout:    'समय समाप्त। माइक क्लिक करके फिर बोलें।',
        placeholder:'उदा: शिवमोगा में हृदय रोग विशेषज्ञ',
        subTitle:   'बीमारी, विशेषज्ञ या अस्पताल का नाम बोलें',
    },
};

// Keyword map: Kannada & Hindi disease/symptom words → English
const KEYWORD_TRANSLATIONS = {
    // ── Kannada ──────────────────────────────────
    'ಎದೆ ನೋವು':       'chest pain',
    'ತಲೆ ನೋವು':       'headache',
    'ಜ್ವರ':            'fever',
    'ಮಧುಮೇಹ':         'diabetes',
    'ರಕ್ತದೊತ್ತಡ':      'blood pressure',
    'ಕಣ್ಣು ವೈದ್ಯ':    'eye doctor',
    'ಕಣ್ಣು ರೋಗ':      'eye disease',
    'ಮಕ್ಕಳ ವೈದ್ಯ':    'pediatrician',
    'ಚರ್ಮ ರೋಗ':       'skin disease',
    'ಮೂಳೆ ವೈದ್ಯ':     'orthopedic',
    'ಹೃದಯ ವೈದ್ಯ':     'cardiologist',
    'ಮೆದುಳು ವೈದ್ಯ':   'neurologist',
    'ಹೊಟ್ಟೆ ನೋವು':    'stomach pain',
    'ಉಸಿರಾಟ ತೊಂದರೆ':  'breathing problem',
    'ಮೂಗು ಕಿವಿ ಗಂಟಲು': 'ENT',
    'ಹಲ್ಲು ವೈದ್ಯ':    'dentist',
    'ಮಹಿಳಾ ವೈದ್ಯ':    'gynecologist',
    'ಸಾಮಾನ್ಯ ವೈದ್ಯ':  'general physician',
    // ── Hindi ────────────────────────────────────
    'सीने में दर्द':   'chest pain',
    'सिरदर्द':         'headache',
    'बुखार':           'fever',
    'मधुमेह':          'diabetes',
    'रक्तचाप':         'blood pressure',
    'आँख का डॉक्टर':  'eye doctor',
    'आँख की बीमारी':  'eye disease',
    'बच्चों का डॉक्टर':'pediatrician',
    'चर्म रोग':        'skin disease',
    'हड्डी का डॉक्टर': 'orthopedic',
    'दिल का दर्द':    'heart pain',
    'दिल के डॉक्टर':  'cardiologist',
    'दिमाग के डॉक्टर': 'neurologist',
    'पेट दर्द':        'stomach pain',
    'सांस की तकलीफ':  'breathing problem',
    'कान नाक गला':    'ENT',
    'दाँत का डॉक्टर': 'dentist',
    'महिला डॉक्टर':   'gynecologist',
    'सामान्य चिकित्सक':'general physician',
    'शिवमोगा':        'Shivamogga',
    'बैंगलोर':        'Bangalore',
    'मैसूर':          'Mysore',
    // ── Time Words ───────────────────────────────
    'ಬೆಳಿಗ್ಗೆ':        'morning',
    'ಮಧ್ಯಾಹ್ನ':       'afternoon',
    'ಸಂಜೆ':           'evening',
    'ರಾತ್ರಿ':          'night',
    'ಇಂದು':           'today',
    'ನಾಳೆ':           'tomorrow',
    'ಈಗ':             'now',
    'ಮಂಗಳೂರು':        'Mangalore',
    'ಉಡುಪಿ':          'Udupi',
    'ಬೆಂಗಳೂರು':       'Bangalore',
    'ಶಿವಮೊಗ್ಗ':       'Shivamogga',
    'ಮೈಸೂರು':         'Mysore',
    'सुबह':           'morning',
    'दोपहर':          'afternoon',
    'शाम':            'evening',
    'रात':            'night',
    'आज':             'today',
    'कल':             'tomorrow',
    'अभी':            'now',
    'मंगलुरु':        'Mangalore',
    'उडुपी':          'Udupi',
    'बेंगलुरु':       'Bangalore',
    'मैसूर':          'Mysore',
    'उडापि':          'Udupi',
    // ── Commands ─────────────────────────────────
    'ರದ್ದುಗೊಳಿಸು':     'cancel',
    'ರದ್ದು ಗೊಳಿಸು':    'cancel',
    'ಕ್ಯಾನ್ಸಲ್':       'cancel',
    'रद्द करें':        'cancel',
    'कैंसिल':          'cancel',
};

/**
 * Translate Kannada/Hindi keywords to English before sending to backend.
 * The backend NLP only understands English terms.
 */
function translateToEnglish(text) {
    let out = text;
    for (const [native, english] of Object.entries(KEYWORD_TRANSLATIONS)) {
        out = out.replace(new RegExp(native, 'g'), english);
    }
    return out;
}

/**
 * Switch voice recognition language + update all UI labels.
 */
function setVoiceLanguage(lang) {
    currentLang = lang;
    
    // CRITICAL: Re-init recognition with new language code to ensure browser sync
    if (recognition) {
        recognition.stop();
        initSpeechRecognition(); 
    }

    // Highlight active button
    document.querySelectorAll('.lang-btn').forEach(btn => btn.classList.remove('active-lang'));
    const ids = { 'en-IN': 'lang-en', 'kn-IN': 'lang-kn', 'hi-IN': 'lang-hi' };
    const activeBtn = document.getElementById(ids[lang]);
    if (activeBtn) activeBtn.classList.add('active-lang');

    // Update UI text
    const L = LANG_LABELS[lang];
    setVoiceStatus(L.clickMic, false);
    
    // Apply full UI translation
    applyUITranslations(lang);

    // Re-load states to update list text
    loadStates();
    if (document.getElementById('state-select').value) {
        onStateChange();
    }
}

// ============ SPEECH RECOGNITION ============
let voiceSilenceTimer = null;
window.sessionTranscript = "";
window.isContinuingSession = false;

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('Speech recognition not supported');
        return;
    }

    recognition = new SpeechRecognition();
    
    // Set continuous to true for all. We'll handle stopping manually via silence timer.
    // This prevents the engine from cutting off after a single Kannada word fragment.
    recognition.continuous     = true; 
    recognition.interimResults = true;     
    recognition.maxAlternatives = 1;       
    recognition.lang           = currentLang || 'kn-IN';

    let aggregatedTranscript = "";

    recognition.onstart = () => {
        isListening = true;
        aggregatedTranscript = ""; 
        updateVoiceUI(true);
        setVoiceStatus(LANG_LABELS[currentLang].listening, true);
        console.log("Speech recognition started.");
    };

    recognition.onresult = (event) => {
        // ALWAYS clear silence timer when ANY sound (interim or final) is heard
        clearTimeout(voiceSilenceTimer);

        // ZERO-INDEX REBUILD STRATEGY:
        // Instead of aggregating changes, we rebuild the entire phrase from the 
        // SpeechRecognitionResultList on every event. This prevents "lost halves".
        let fullTranscript = "";
        for (let i = 0; i < event.results.length; i++) {
            fullTranscript += event.results[i][0].transcript;
        }

        const displayTranscript = fullTranscript.trim();

        if (displayTranscript) {
            const cleaned = cleanTranscript(displayTranscript);
            showTranscript(cleaned);
            setVoiceStatus(LANG_LABELS[currentLang].gotIt, true);
        }

        // Restart 5s silence timer (increased for Indic language sentence flow)
        voiceSilenceTimer = setTimeout(() => {
            if (isListening) {
                console.log("Silence detected: 5s threshold reached. Processing full sentence.");
                recognition.stop();
            }
        }, 5000); 
    };

    recognition.onend = () => {
        console.log("Speech recognition ended.");
        isListening = false;
        updateVoiceUI(false);
        clearTimeout(voiceSilenceTimer);

        const currentText = document.getElementById('transcript-text').textContent;
        // Reduced threshold from 5 to 2 to support short words like "Fever", "Cold"
        if (currentText && currentText.trim().length >= 2) {
            processVoiceText();
        } else {
            setVoiceStatus(LANG_LABELS[currentLang].clickMic, false);
        }
    };

    recognition.onerror = (event) => {
        console.error("Speech Recognition Error:", event.error);
        isListening = false;
        updateVoiceUI(false);
        clearTimeout(voiceSilenceTimer);

        if (event.error === 'no-speech') {
            setVoiceStatus(LANG_LABELS[currentLang].noSpeech, false);
        } else if (event.error === 'network') {
            setVoiceStatus('Network error. Click to retry.', false);
        } else {
            setVoiceStatus('Mic Error: ' + event.error, false);
        }
    };
}

/**
 * Remove filler/noise words, collapse spaces, capitalise first letter.
 */
function cleanTranscript(text) {
    // Improved filler removal that doesn't break Unicode words
    const fillers = /\b(um+|uh+|hmm*|ah+|er+|uhh|mm+|okay so|so um|like um|you know|i mean)\b/gi;
    return text
        .trim()
        .replace(fillers, '')
        .replace(/\s{2,}/g, ' ')
        // Ensure first character capitalization only if it's an ASCII letter
        .replace(/^[a-z]/i, c => c.toUpperCase())
        .trim();
}

function toggleVoice() {
    if (!recognition) return showToast('Use Chrome for Voice Features.', 'error');
    if (isListening) {
        recognition.stop();
        clearTimeout(voiceSilenceTimer);
    } else {
        // Always reset — mic only starts on explicit user click
        hideElement('booking-flow-results');
        hideElement('intent-preview');
        hideElement('booking-result');
        document.getElementById('transcript-text').textContent = "";
        window.sessionTranscript = "";
        window.isContinuingSession = false;
        recognition.start();

        // Initial safety net: if user doesn't speak at ALL for 8s (increased), turn off mic.
        voiceSilenceTimer = setTimeout(() => {
            const currentText = document.getElementById('transcript-text').textContent;
            if (isListening && !currentText) {
                console.log("Initial timeout: No speech detected in 8s.");
                recognition.stop();
                setVoiceStatus(LANG_LABELS[currentLang].timeout, false);
            }
        }, 8000);
    }
}

function updateVoiceUI(isL) {
    const vis = document.getElementById('voice-visualizer');
    const btn = document.getElementById('mic-button');
    if (isL) {
        vis.classList.add('listening');
        btn.classList.add('listening');
    } else {
        vis.classList.remove('listening');
        btn.classList.remove('listening');
        // Do not automatically clear status here to allow "Processing" or "Timeout" to persist
    }
}

function setVoiceStatus(t, active) {
    const el = document.getElementById('voice-status');
    el.textContent = t;
    el.className = 'voice-status' + (active ? ' active' : '');
}

function showTranscript(text) {
    document.getElementById('transcript-area').classList.remove('hidden');
    document.getElementById('transcript-text').textContent = text;
}

function retryVoice() {
    hideElement('transcript-area');
    hideElement('intent-preview');
    hideElement('booking-result');
    setVoiceStatus('Click the mic to speak', false);
}


// ============ BOOKING PIPELINE ============
async function processManualText() {
    const input = document.getElementById('manual-text');
    const text = input.value.trim();
    if (!text) return;
    showTranscript(text);
    await processVoiceText();
    input.value = '';
}

async function autoUpdateDistrictFromVoice(stateName, districtName) {
    if (!stateName || !districtName) return;

    console.log(`Syncing Location: ${districtName}, ${stateName}`);

    const norm = (s) => s.toLowerCase().trim().replace(/[^a-z0-9]/g, '');
    const dNorm = norm(districtName);

    // 1. Target & update State dropdown
    const stateSelect = document.getElementById('state-select');
    const stateOpt = Array.from(stateSelect.options).find(o => 
        norm(o.text).includes(norm(stateName)) || norm(stateName).includes(norm(o.text))
    );
    
    if (stateOpt) {
        stateSelect.value = stateOpt.value;
        currentSelectedState = stateOpt.text;
        
        try {
            // Fetch districts for this state
            const res = await fetch(`${API_BASE}/states/${stateOpt.value}/districts`);
            districtsData = await res.json();
            
            const districtSelect = document.getElementById('district-select');
            districtSelect.innerHTML = `<option value="" disabled selected>Select District</option>` +
                districtsData.map(d => `<option value="${d.district_id}">${d.district_name}</option>`).join('');
            districtSelect.disabled = false;

            // 2. Try match district
            const distOpt = Array.from(districtSelect.options).find(o => {
                const optNorm = norm(o.text);
                return optNorm.includes(dNorm) || dNorm.includes(optNorm) || 
                       (dNorm.startsWith('shimoga') && optNorm.includes('shivamogga'));
            });

            if (distOpt) {
                districtSelect.value = distOpt.value;
                const distData = districtsData.find(d => d.district_id == distOpt.value);
                if (distData) {
                    currentSelectedDistrict = distData.district_name;
                    window._districtLat = distData.latitude;
                    window._districtLng = distData.longitude;
                    console.log(`Dropdown Synced: ${distData.district_name}`);
                }
            } else {
                console.warn(`No dropdown match for ${districtName}, using geocoder fallback`);
                await zoomMapToDistrict(districtName, stateName);
            }
        } catch (e) {
            console.error("Failed to sync location UI", e);
        }
    }
}

async function zoomMapToDistrict(district, state) {
    try {
        const query = `${district},${state},India`;
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`;
        const res = await fetch(url);
        const results = await res.json();
        if (results && results.length > 0) {
            const lat = parseFloat(results[0].lat);
            const lon = parseFloat(results[0].lon);
            map.setView([lat, lon], 11, { animate: true });
            
            // Re-sync local district GPS for markers filtering
            window._districtLat = lat;
            window._districtLng = lon;
        }
    } catch (e) {
        console.error("Nominatim Lookup Error:", e);
    }
}

async function processVoiceText() {
    const text = document.getElementById('transcript-text').textContent;
    if (!text) return;

    const btn = document.getElementById('mic-button'); // Fix: Define btn for use in finally block
    setVoiceStatus(LANG_LABELS[currentLang].gotIt, true);

    try {
        const payload = {
            // Translate Kannada/Hindi keywords → English before sending to NLP backend
            text: translateToEnglish(text),
            patient_name: 'Voice User',
            district: currentSelectedDistrict,
            state: currentSelectedState,
            // Pass logged-in receptionist email so notifications go to correct inbox
            receptionist_email: currentUser ? currentUser.email : null,
            time_slot: document.getElementById('selected-time-slot')?.value || null
        };

        const response = await fetch(`${API_BASE}/voice/book`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        document.getElementById('booking-flow-results').classList.remove('hidden');

        if (data.intent) showIntentPreview(data.intent);

        showBookingResult(data);

        if (data.success && data.matched_hospital) {
            const h = data.matched_hospital;
            
            // 1. Sync UI dropdowns/internal state to the booked location
            await autoUpdateDistrictFromVoice(h.state_name, h.district_name);
            
            // 2. Clear previous markers and reload specifically for this district
            // Pass the hospital_id so it gets highlighted (purple) and its popup opens
            await fetchAndMapHospitals(h.district_name, h.hospital_id, h.state_name);
            
            // Map zooming is handled naturally to the district level (11) by fetchAndMapHospitals
        } else if (data.intent && data.intent.district) {
            // Partial detection: Update map even if booking isn't confirmed yet
            const dist = data.intent.district;
            const state = data.intent.state || currentSelectedState;
            await autoUpdateDistrictFromVoice(state, dist);
            await zoomMapToDistrict(dist, state);
            await fetchAndMapHospitals(dist, null, state);
        }

        if (data.success) {
            let mapPanel = document.getElementById('map-floating-panel');
            if (mapPanel) {
                mapPanel.classList.remove('hidden');
                document.getElementById('panel-found-nodes').textContent = data.found_nodes || '0';
                document.getElementById('panel-max-rating').textContent = data.matched_hospital.rating || '4.5';
                document.getElementById('panel-booked-hospital').textContent = data.matched_hospital.hospital_name;
                document.getElementById('panel-district').textContent = data.matched_hospital.district_name;
                document.getElementById('panel-specialist').textContent = data.appointment.specialization || 'General Specialist';
                document.getElementById('panel-token').textContent = data.token_number || (data.appointment.appointment_id + 100);
            }

            speakResponse(data.message);
            showToast(`Email sent successfully to ${data.email_sent_to || 'admin@gmail.com'}`, 'success');
        } else {
            speakResponse(data.message);
        }

    } catch (error) {
        console.error("Voice Booking Error:", error);
        showBookingResult({ success: false, message: 'Server connection failed or timed out.' });
        speakResponse("I'm sorry, I'm having trouble connecting to the server. Please try again.");
    } finally {
        btn.textContent = '🚀 Find & Auto-Book';
        btn.disabled = false;
        document.getElementById('transcript-area').classList.add('hidden');
        setVoiceStatus(LANG_LABELS[currentLang].clickMic, false);
    }
}

function showIntentPreview(intent) {
    const container = document.getElementById('intent-preview');
    const grid = document.getElementById('intent-grid');
    container.classList.remove('hidden');

    const items = [
        { label: 'Disease / Symptom', value: intent.disease || '—' },
        { label: 'Specialty Required', value: intent.specialization || '—' },
        { label: 'Map District', value: intent.district || 'Any' },
        { label: 'Specific Hospital', value: intent.hospital_name || 'AI Matched Best' },
    ];

    grid.innerHTML = items.map(item => `
        <div class="intent-chip">
            <span class="intent-chip-label">${item.label}</span>
            <span class="intent-chip-value">${item.value}</span>
        </div>
    `).join('');
}

function showBookingResult(data) {
    const container = document.getElementById('booking-result');
    const content = document.getElementById('result-content');
    container.classList.remove('hidden');

    if (data.success) {
        container.className = 'booking-result success';
        const h = data.matched_hospital;
        const a = data.appointment;

        content.innerHTML = `
            <div style="font-size: 32px; margin-bottom: 10px;">✅</div>
            <h3 style="color: #166534; margin-bottom: 10px;">Booking Confirmed</h3>
            <p style="margin-bottom: 15px;">${data.message}</p>
            <div style="background: white; padding: 15px; border-radius: 8px;">
                <p><strong>Hospital:</strong> ${h.hospital_name}</p>
                <p><strong>Specialty:</strong> ${a.specialization || 'General'}</p>
                <p><strong>District:</strong> ${h.district_name}, ${h.state_name}</p>
                <p><strong>Rating:</strong> ⭐ ${h.rating || 4.5}</p>
                <p><strong>Token Number:</strong> ${data.token_number || (a.appointment_id + 1000)}</p>
                <p><strong>Schedule:</strong> <span class="loc-badge">${a.date} at ${a.time}</span></p>
            </div>
            ${data.email_sent_to ? `
            <div style="background: #ecfdf5; padding: 10px; border-radius: 8px; border: 1px solid #10b981; color: #047857; font-size: 13px; margin-top: 15px; text-align: center;">
                📧 Email sent successfully to: <strong>${data.email_sent_to}</strong>
            </div>` : `
            <div style="background: #f1f5f9; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; color: #475569; font-size: 13px; margin-top: 15px; text-align: center;">
                📧 Email sent successfully to: <strong>admin@gmail.com</strong>
            </div>`}
        `;
    } else if (data.message.includes("almost ready") || data.message.includes("Please mention")) {
        // Friendly Warning instead of Error for missing fields
        container.className = 'booking-result warning';
        content.innerHTML = `
            <div style="font-size: 32px; margin-bottom: 10px;">⏳</div>
            <h3 style="color: #d97706; margin-bottom: 10px;">Almost Ready!</h3>
            <p style="color: #92400e; font-weight: 500;">${data.message}</p>
            <p style="font-size: 13px; color: #b45309; margin-top: 10px;">Click the mic again to provide this detail.</p>
        `;
    } else {
        // Actual hard error
        container.className = 'booking-result error';
        content.innerHTML = `
            <div style="font-size: 32px; margin-bottom: 10px;">⚠️</div>
            <h3 style="color: #991b1b; margin-bottom: 10px;">Booking Failed</h3>
            <p>${data.message}</p>
        `;
    }
}

// ============ TEXT TO SPEECH ============
function speakResponse(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    // Sanitize text for natural pronunciation:
    // Convert raw slot formats '9:00 AM – 11:00 AM' -> 'between 9 AM to 11 AM'
    let spokenText = text
        .replace(/(\d{1,2}):(00)\s*(AM|PM)/g, '$1 $3')      // drop ':00' -> '9 AM'
        .replace(/\s*[\u2013\u2014\-]{1,2}\s*/g, ' to ')      // en-dash -> 'to'
        .replace(/Token Number:/gi, 'Token Number is')         // natural phrasing
        .trim();

    const utterance = new SpeechSynthesisUtterance(spokenText);
    utterance.lang = 'en-IN';
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
}


// ============ ALL HOSPITALS DATABASE ============
async function loadAllHospitals() {
    try {
        let url = `${API_BASE}/hospitals`;
        
        // Use URLSearchParams for clean query building
        const params = new URLSearchParams();

        // 1. Specialization Filter
        const spec_filter = document.getElementById('hosp-filter-specialty')?.value;
        if (spec_filter) params.append('specialization', spec_filter);

        // 2. State Filter
        const state_filter_id = document.getElementById('hosp-filter-state')?.value;
        if (state_filter_id && statesData) {
            const target_state = statesData.find(s => s.state_id == state_filter_id)?.state_name;
            if (target_state) params.append('state_name', target_state);
        }

        const queryString = params.toString();
        if (queryString) url += `?${queryString}`;

        const res = await fetch(url);
        const hospitals = await res.json();


        const grid = document.getElementById('hospitals-grid');
        if (!grid) return;

        if (hospitals.length === 0) {
            grid.innerHTML = `<p class="text-center w-100" style="grid-column: 1/-1;">No hospitals found for this filter.</p>`;
            return;
        }

        grid.innerHTML = hospitals.map(h => `
            <div class="hospital-card">
                <div class="mb-3">
                    <span class="hosp-badge rate-badge">⭐ ${h.rating} Rating</span>
                    <span class="hosp-badge loc-badge">📍 ${h.district_name}</span>
                </div>
                <h3 class="mb-2" style="font-size:18px;">${h.hospital_name}</h3>
                <p class="mb-3" style="font-size:13px; color:#64748b;">${h.state_name}</p>
                
                <div style="margin-bottom: 10px;">
                    <strong style="font-size:13px; display:block; margin-bottom:5px;">Top Specialties:</strong>
                    ${h.specializations.split(',').slice(0, 3).map(s =>
            `<span class="hosp-badge spec-badge">${s.trim()}</span>`
        ).join('')}
                </div>
                
                <div style="border-top: 1px solid #e2e8f0; padding-top:10px; margin-top:15px; font-size: 13px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>Doctors: <strong>${h.available_doctors}+</strong></span>
                        <a href="#" style="color:#4f46e5; text-decoration:none;" onclick="event.preventDefault(); showPage('booking')">Map View →</a>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load hospitals:', err);
    }
}


// ============ AUTH / DASHBOARD ============
async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const errorDiv = document.getElementById('login-error');
    errorDiv.style.display = 'none';
    btn.textContent = 'Authenticating...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('login-email').value.trim(),
                password: document.getElementById('login-password').value
            }),
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Invalid email or password');
        }

        const data = await res.json();
        authToken = data.access_token;
        currentUser = data.receptionist;
        localStorage.setItem('smartclinic_token', authToken);

        errorDiv.style.display = 'none';
        updateNavForAuth();
        showPage('dashboard');
        showToast('Login Successful', 'success');
    } catch (err) {
        errorDiv.textContent = '❌ ' + (err.message || 'Login failed. Please check your credentials.');
        errorDiv.style.display = 'block';
        showToast('Login Failed', 'error');
    } finally {
        btn.textContent = 'Access Dashboard';
        btn.disabled = false;
    }
}

function switchAuthTab(tab) {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const subtitle = document.getElementById('auth-subtitle');
    const footerHint = document.getElementById('auth-footer-hint');

    // Clear error messages when switching tabs
    const loginError = document.getElementById('login-error');
    const registerError = document.getElementById('register-error');
    const registerSuccess = document.getElementById('register-success');
    if (loginError) loginError.style.display = 'none';
    if (registerError) registerError.style.display = 'none';
    if (registerSuccess) registerSuccess.style.display = 'none';

    if (tab === 'login') {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        tabLogin.style.background = 'linear-gradient(135deg, #4f46e5, #ec4899)';
        tabLogin.style.color = '#fff';
        tabRegister.style.background = '#f8fafc';
        tabRegister.style.color = '#64748b';
        subtitle.textContent = 'Sign in to manage maps and DB';
        footerHint.innerHTML = 'Don\'t have an account? <a href="#" onclick="switchAuthTab(\'register\'); return false;" style="color:#4f46e5; font-weight:600;">Register here</a>';
    } else {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
        tabRegister.style.background = 'linear-gradient(135deg, #4f46e5, #ec4899)';
        tabRegister.style.color = '#fff';
        tabLogin.style.background = '#f8fafc';
        tabLogin.style.color = '#64748b';
        subtitle.textContent = 'Create a new admin account';
        footerHint.innerHTML = 'Already have an account? <a href="#" onclick="switchAuthTab(\'login\'); return false;" style="color:#4f46e5; font-weight:600;">Sign in here</a>';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = document.getElementById('register-btn');
    const errorDiv = document.getElementById('register-error');
    const successDiv = document.getElementById('register-success');
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    btn.textContent = 'Creating Account...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: document.getElementById('register-name').value.trim(),
                email: document.getElementById('register-email').value.trim(),
                password: document.getElementById('register-password').value,
            }),
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Registration failed');
        }

        const data = await res.json();
        authToken = data.access_token;
        currentUser = data.receptionist;
        localStorage.setItem('smartclinic_token', authToken);

        errorDiv.style.display = 'none';
        updateNavForAuth();
        showPage('dashboard');
        showToast('Account created successfully!', 'success');
    } catch (err) {
        errorDiv.textContent = '❌ ' + (err.message || 'Registration failed. Please try again.');
        errorDiv.style.display = 'block';
        showToast(err.message || 'Registration Failed', 'error');
    } finally {
        btn.textContent = 'Create Account';
        btn.disabled = false;
    }
}

async function checkAuth() {
    if (!authToken) return;
    try {
        const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        if (res.ok) {
            currentUser = await res.json();
            updateNavForAuth();
        } else {
            handleLogout();
        }
    } catch (e) { }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('smartclinic_token');
    updateNavForAuth();
    showPage('home');
}

async function loadDashboard() {
    if (!authToken) { showPage('login'); return; }

    try {
        document.getElementById('dash-user-name').textContent = currentUser.name;

        const statsRes = await fetch(`${API_BASE}/stats`);
        const stats = await statsRes.json();
        document.getElementById('stat-hospitals').textContent = stats.total_hospitals;
        document.getElementById('stat-appointments').textContent = stats.total_appointments;
        document.getElementById('stat-confirmed').textContent = stats.confirmed_appointments;
        document.getElementById('stat-cancelled').textContent = stats.cancelled_appointments;

        const apptRes = await fetch(`${API_BASE}/appointments`);
        const appointments = await apptRes.json();

        const tbody = document.getElementById('appointments-tbody');
        const empty = document.getElementById('no-appointments');

        if (appointments.length === 0) {
            tbody.innerHTML = '';
            empty.classList.remove('hidden');
        } else {
            empty.classList.add('hidden');
            tbody.innerHTML = appointments.map(a => `
                <tr>
                    <td>#${a.appointment_id}</td>
                    <td><strong>${a.hospital ? a.hospital.hospital_name : 'N/A'}</strong></td>
                    <td>${a.hospital ? a.hospital.district_name : 'N/A'}</td>
                    <td>${a.patient_name}</td>
                    <td>${a.date} <br> <small>${a.time}</small></td>
                    <td><span class="hosp-badge ${a.status === 'confirmed' ? 'rate-badge' : 'danger-badge'}">${a.status}</span></td>
                    <td>
                        <button class="btn btn-outline borderless p-1" onclick="cancelAppointment(${a.appointment_id})" title="Cancel Appointment">🚫 Cancel</button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Dashboard error:', err);
    }
}

async function cancelAppointment(id) {
    if (!confirm('Cancel this appointment? (It will not be deleted, only marked as cancelled)')) return;
    try {
        await fetch(`${API_BASE}/appointments/${id}/cancel`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        loadDashboard();
        showToast('Appointment Cancelled', 'info');
    } catch (e) {
        showToast('Error cancelling appointment', 'error');
    }
}

// ============ UTILS ============
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> ${message}`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
}

function hideElement(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
}
