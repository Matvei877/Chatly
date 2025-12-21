import { useState } from 'react';
import { useSwipeable } from 'react-swipeable';
import './App.css';

// 1. ИМПОРТИРУЕМ КАРТИНКУ
// Если для каждого слайда нужна своя картинка, импортируйте несколько
import shapeImage from './assets/shape1.png'; 

const slides = [
  {
    id: 15,
    color: '#B9A3DB',
    indicatorIndex: 0,
    image: shapeImage,
    // ВМЕСТО ОБЫЧНОГО ТЕКСТА ПИШЕМ JSX:
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
    // Для второго слайда можно оставить как было, или тоже переделать:
    title: (
      <>
        Самые<br /><span style={{ color: '#3D5258' }}>популярные<br />слова</span>
      </>
    )
  }
];

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);

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
  
  // (Код функции handleShare остался прежним...)
  const handleShare = () => {}; 

  const handlers = useSwipeable({
    onSwipedLeft: () => handleNext(),
    onSwipedRight: () => handlePrev(),
    preventScrollOnSwipe: true,
    trackMouse: true
  });

  const currentSlide = slides[currentIndex];

  return (
    <div className="main-container" {...handlers}>
      
      <div className="white-header"></div>

      <div 
        className="colored-section" 
        style={{ backgroundColor: currentSlide.color }}
      >
        {/* 2. ВСТАВЛЯЕМ КАРТИНКУ ФОНА */}
        {/* Она должна быть перед индикаторами в коде, либо регулироваться z-index */}
        <img 
          src={currentSlide.image} 
          alt="" 
          className="bg-image" 
        />

        {/* Индикаторы */}
        <div className="indicators-wrapper">
          {[0, 1, 2].map((idx) => (
            <div 
              key={idx} 
              className={`indicator ${idx === currentSlide.indicatorIndex ? 'active' : ''}`}
            />
          ))}
        </div>

        {/* --- НОВАЯ ЧАСТЬ: ЗАГОЛОВОК --- */}
        <h1 className="slide-title">
          {currentSlide.title}
        </h1>
        {/* ------------------------------- */}

      </div>

      <div className="white-footer">
        <div className="buttons-container">
          <button className="btn btn-share" onClick={handleShare}>
            поделиться
            {/* SVG иконка... */}
          </button>
          <button className="btn btn-next" onClick={handleNext}>
            дальше
            {/* SVG иконка... */}
          </button>
        </div>
      </div>

    </div>
  );
}

export default App;