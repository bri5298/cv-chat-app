export type FaqItem = {
  question: string;
  answer: string[];
};

export const faqItems: FaqItem[] = [
  {
    question: "Who is Brielle?",
    answer: [
      "Hi there, my name is Brielle and I created this app. You'll be able to dive into my work experience with it, but first, here is some general information about me.",
      "I take a lot of pride in doing good work. Over the years, I've often been told that I'm someone people can hand a problem to and trust that I'll figure it out. It's one of the best compliments I've ever received.",
      "I also care a lot about being someone people can count on. I like helping others work through problems, answer questions, or learn something new. Seeing someone leave a conversation feeling more confident than when they started is always rewarding.",
      "Outside of work, I like staying active, going on walks with my dog, and ending the day with a good TV show.",
    ],
  },
  {
    question: "Why this app?",
    answer: [
      "I got the idea for this app after being part of the hiring process and going through CVs for a new role on our team. After reading through a lot of them, I noticed that it can be hard to understand what really sets one candidate apart from another.",
      "I wanted to create something that would help me stand out in a more personal and useful way. Instead of only asking someone to read through my CV, this app lets them ask questions directly in an interactive and efficient way.",
      "It also felt like a good way to show my development skills through something real, instead of just listing them on a resume.",
    ],
  },
];