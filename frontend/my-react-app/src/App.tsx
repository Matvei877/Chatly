import { useState, useEffect } from 'react';
import { useSwipeable } from 'react-swipeable';
import './App.css';

import shapeImage from './assets/shape1.png'; 


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
  const [loading, setLoading] = useState(true); 

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    
    
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
  
  const handleShare = async () => {
    const params = new URLSearchParams(window.location.search);
    const chatId = params.get('id');

    if (!chatId) return;

    // @ts-ignore
    if (window.Telegram && window.Telegram.WebApp) {
        // @ts-ignore
        window.Telegram.WebApp.close();
    }

    try {
      await fetch(`${API_URL}/api/share/${chatId}`, {
        method: 'POST',
      });
    } catch (error) {
      console.error("Ошибка при отправке статистики:", error);
    }
  };

  const handlers = useSwipeable({
    onSwipedLeft: () => handleNext(),
    onSwipedRight: () => handlePrev(),
    preventScrollOnSwipe: true,
    trackMouse: true
  });

  const currentSlide = slides[currentIndex];

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

        {currentIndex === 0 && stats && stats.active_user && (
          <>
            <div className="stats-left-container">
              <div className="big-number">
                {stats.active_user.count}
              </div>
              <div className="big-number-label">
                сообщений
              </div>
            </div>

            <div className="hero-avatar-container">
               {stats.active_user.avatar_url ? (
                  <img 
                    src={stats.active_user.avatar_url} 
                    alt="Avatar" 
                    className="hero-avatar"
                  />
               ) : (
                  <div className="hero-avatar-placeholder">
                    {stats.active_user.name[0]}
                  </div>
               )}
            </div>

            <div className="bottom-description-text">
              <span style={{ fontWeight: 'bold' }}>{stats.active_user.name}</span> написал больше всего сообщений в чате ({stats.active_user.count}) !
            </div>
          </>
        )}

        {currentIndex === 1 && stats && stats.top_words && stats.top_words.length >= 2 && (
          <>
            <div className="top-words-list">
              {stats.top_words.slice(0, 3).map((item: any, index: number) => (
                <div key={index} className="top-word-item">
                  {index + 1}. {item.word}
                </div>
              ))}
            </div>

            {stats.top_words.length > 0 && (
              <div className="bottom-description-text">
                <span style={{ fontWeight: 'bold', display: 'block', marginBottom: '4px' }}>
                  Было использовано
                </span>
                более {stats.top_words[0].count} слов <br/>
                “{stats.top_words[0].word}” !
              </div>
            )}
          </>
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