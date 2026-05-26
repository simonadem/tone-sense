// POINTER HOMEPAGE keeps track of current slides
let slideTrackers = {
  "mySlides": 1,
  "trendSlides": 1,
  "privSlides": 1
};

//functions that  match the onclick in html
function plusSlides(n) { moveSlides(n, "mySlides"); }
function plusTrendSlides(n) { moveSlides(n, "trendSlides"); }
function plusPrivSlides(n) { moveSlides(n, "privSlides"); }

// main function
function moveSlides(n, className) {
  // updates the specific counter 
  slideTrackers[className] += n;
  
  let slides = document.getElementsByClassName(className);
  let currentIndex = slideTrackers[className];

  // resets to one at last slide
  if (currentIndex > slides.length) { slideTrackers[className] = 1; }
  // goes to last slide if we go below one
  if (currentIndex < 1) { slideTrackers[className] = slides.length; }

  // loops through the slides in the group
  for (let i = 0; i < slides.length; i++) {
    slides[i].style.display = "none";
  }

  // displays recently updated slide
  let finalIndex = slideTrackers[className];
  slides[finalIndex - 1].style.display = "block";
}
