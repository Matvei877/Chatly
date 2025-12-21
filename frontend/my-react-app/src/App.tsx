import { useState, useEffect } from 'react';
import { useSwipeable } from 'react-swipeable';
import './App.css';

import shapeImage from './assets/shape1.png'; 

// Убедитесь, что ссылка правильная (без слэша в конце)
const API_URL = "https://chatly-backend-nflu.onrender.com"; 

const slides = [
  {
    id: 15,
    color: '#B9A3DB',
    indicatorIndex: 0,
    image: shapeImage,
    title: (
      <>
        Самый активный<br /><span style={{ color: '#52546F' }}>участник</span>
      </>
    )
  },
  {
    id: 16,
    color: '#55C2BC',
    indicatorIndex: 1,
    image: shapeImage,
    title: (
      <>
        Самые<br /><span style={{ color: '#3D5258' }}>популярные<br />слова</span>
      </>
    )
  }
];

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true); // Добавили состояние загрузки

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    
    // 1. ИЗМЕНЕНИЕ: Ищем параметр 'id', так как бот отправляет ?id=...
    const chatId = params.get('id'); 

    if (chatId) {
      fetch(`${API_URL}/api/chat/${chatId}`)
        .then(res => res.json())
        .then(data => {
          console.log("Stats loaded:", data);
          setStats(data);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const handleNext = () => {
    if (currentIndex < slides.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };
  
  const handleShare = () => {}; 

  const handlers = useSwipeable({
    onSwipedLeft: () => handleNext(),
    onSwipedRight: () => handlePrev(),
    preventScrollOnSwipe: true,
    trackMouse: true
  });

  const currentSlide = slides[currentIndex];

  // Если идет загрузка или нет данных
  if (loading) return <div className="white-header">Загрузка...</div>;
  if (!stats && !loading) return <div className="white-header">Нет данных (откройте через бота)</div>;

  return (
    <div className="main-container" {...handlers}>
      
      <div className="white-header"></div>

      <div 
        className="colored-section" 
        style={{ backgroundColor: currentSlide.color }}
      >
        <img src={currentSlide.image} alt="" className="bg-image" />

        {/* === СЛАЙД 1: АВАТАРКА === */}
        {currentIndex === 0 && stats.active_user && (
          <div className="avatar-container">
            {stats.active_user.avatar_url ? (
              <img 
                src={stats.active_user.avatar_url} 
                alt="Avatar" 
                className="user-avatar"
              />
            ) : (
              <div className="user-avatar-placeholder">
                 {stats.active_user.name[0]}
              </div>
            )}
            <div className="user-name-overlay">
               {stats.active_user.name}
            </div>
            <div className="user-count-overlay">
               {stats.active_user.count} сообщений
            </div>
          </div>
        )}

        {/* === СЛАЙД 2: СЛОВА (НОВОЕ) === */}
        {currentIndex === 1 && stats.top_words && (
          <div className="words-container">
            {stats.top_words.map((item: any, index: number) => (
              <div key={index} className="word-bubble">
                <span className="word-text">{item.word}</span>
                <span className="word-count">{item.count}</span>
              </div>
            ))}
          </div>
        )}

        <div className="indicators-wrapper">
          {[0, 1].map((idx) => (
            <div 
              key={idx} 
              className={`indicator ${idx === currentSlide.indicatorIndex ? 'active' : ''}`}
            />
          ))}
        </div>

        <h1 className="slide-title">
          {currentSlide.title}
        </h1>

      </div>

      <div className="white-footer">
        <div className="buttons-container">
          <button className="btn btn-share" onClick={handleShare}>поделиться</button>
          <button className="btn btn-next" onClick={handleNext}>дальше</button>
        </div>
      </div>
    </div>
  );
}

export default App;