import React, { useState, useMemo } from 'react';
import {
  Film,
  Play,
  CheckCircle2,
  Calendar,
  User,
  Award,
  Trophy,
  Trash2,
  Edit3,
  Plus,
  Search,
  ArrowLeft,
  Lock,
  Code,
  Download,
  BookOpen,
  Terminal,
  Copy,
  Check,
  RotateCcw,
  Sparkles,
  ThumbsUp,
  X,
  Share2,
  ShieldCheck,
  Database,
  Layers,
  HelpCircle
} from 'lucide-react';
import { PROJECT_FILES } from './projectFiles';

// --- Types ---
interface UserAccount {
  id: number;
  name: string;
  username: string;
}

interface MovieChoice {
  id: number;
  movieNightId: number;
  title: string;
  genre: string;
  reason: string;
  posterUrl: string;
  trailerUrl?: string;
  trailerEmbedUrl?: string;
}

interface Vote {
  id: number;
  movieNightId: number;
  movieChoiceId: number;
  userId: number;
}

interface MovieNight {
  id: number;
  creatorId: number;
  creatorName: string;
  creatorUsername: string;
  title: string;
  date: string;
  category: 'Comedy' | 'Action' | 'Animation' | 'Other';
  description: string;
  status: 'open' | 'finalized';
  finalMovieId: number | null;
}

// Initial Seed Users
const DEMO_USERS: UserAccount[] = [
  { id: 1, name: 'Alex Rivera', username: 'alex' },
  { id: 2, name: 'Jordan Lee', username: 'jordan' },
  { id: 3, name: 'Sam Chen', username: 'sam' },
];

// Initial Seed Movie Nights
const INITIAL_NIGHTS: MovieNight[] = [
  {
    id: 1,
    creatorId: 1,
    creatorName: 'Alex Rivera',
    creatorUsername: 'alex',
    title: 'Friday Night Comedy Blast',
    date: '2026-10-24',
    category: 'Comedy',
    description: 'Kicking back this Friday with laughs, fresh hot popcorn, and top comedy picks! Cast your vote for the funniest movie to watch.',
    status: 'open',
    finalMovieId: null,
  },
  {
    id: 2,
    creatorId: 2,
    creatorName: 'Jordan Lee',
    creatorUsername: 'jordan',
    title: 'Studio Ghibli & Modern Animation',
    date: '2026-10-18',
    category: 'Animation',
    description: 'A celebration of breathtaking animated storytelling, timeless visuals, and epic soundtracks. Final winner has been decided!',
    status: 'finalized',
    finalMovieId: 5,
  },
  {
    id: 3,
    creatorId: 3,
    creatorName: 'Sam Chen',
    creatorUsername: 'sam',
    title: 'High-Octane Action Night',
    date: '2026-11-02',
    category: 'Action',
    description: 'Edge-of-your-seat thrills, high-stakes heists, and mind-bending action cinema.',
    status: 'open',
    finalMovieId: null,
  },
];

// Initial Movie Choices
const INITIAL_CHOICES: MovieChoice[] = [
  {
    id: 1,
    movieNightId: 1,
    title: 'Superbad',
    genre: 'Comedy / Coming of Age',
    reason: 'Hilarious high school adventure with unmatched comedic chemistry between Jonah Hill and Michael Cera.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/ek8e8txUyUwd2BNqj6lFEerJqUM.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=4eaZ_48ZYog',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/4eaZ_48ZYog?rel=0',
  },
  {
    id: 2,
    movieNightId: 1,
    title: 'Knives Out',
    genre: 'Comedy / Mystery',
    reason: 'Witty, hilarious whodunit packed with eccentric characters, brilliant writing, and laugh-out-loud moments.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/pThyQovXQrw2m0s9x82twj48Jq4.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=qGqiHJTsRkQ',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/qGqiHJTsRkQ?rel=0',
  },
  {
    id: 3,
    movieNightId: 1,
    title: 'The Grand Budapest Hotel',
    genre: 'Comedy / Adventure',
    reason: 'Wes Anderson masterpiece with visually stunning humor, quirky charm, and Ralph Fiennes at his comedic peak.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/eWdyYQreja6JGCzqHWX9NZkt5BW.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=1Fg5iWmQjwk',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/1Fg5iWmQjwk?rel=0',
  },
  {
    id: 4,
    movieNightId: 2,
    title: 'Spirited Away',
    genre: 'Animation / Fantasy',
    reason: 'Hayao Miyazaki legendary Oscar-winning wonder that captivates with stunning fantasy worldbuilding.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=ByXuk9QqQkk',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/ByXuk9QqQkk?rel=0',
  },
  {
    id: 5,
    movieNightId: 2,
    title: 'Spider-Man: Into the Spider-Verse',
    genre: 'Animation / Action',
    reason: 'Groundbreaking animation style, electric soundtrack, and the definitive modern superhero origin story.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=tg52up16eq0',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/tg52up16eq0?rel=0',
  },
  {
    id: 6,
    movieNightId: 3,
    title: 'Mad Max: Fury Road',
    genre: 'Action / Sci-Fi',
    reason: 'Non-stop, practical-effects adrenaline rush that revolutionized modern cinematic action sequences.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/8tZYtuWezp8JbcsvHYO0O46tFbo.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=hEJnMQG9ev8',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/hEJnMQG9ev8?rel=0',
  },
  {
    id: 7,
    movieNightId: 3,
    title: 'Inception',
    genre: 'Action / Sci-Fi Thriller',
    reason: 'Mind-bending dream-heist thriller with Christopher Nolan’s signature tension and iconic rotating hallway combat.',
    posterUrl: 'https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg',
    trailerUrl: 'https://www.youtube.com/watch?v=YoHD9XEInc0',
    trailerEmbedUrl: 'https://www.youtube-nocookie.com/embed/YoHD9XEInc0?rel=0',
  },
];

// Initial Votes
const INITIAL_VOTES: Vote[] = [
  { id: 1, movieNightId: 1, movieChoiceId: 2, userId: 2 }, // Jordan voted for Knives Out
  { id: 2, movieNightId: 1, movieChoiceId: 1, userId: 3 }, // Sam voted for Superbad
  { id: 3, movieNightId: 2, movieChoiceId: 5, userId: 1 }, // Alex voted for Spider-Verse
  { id: 4, movieNightId: 2, movieChoiceId: 5, userId: 2 }, // Jordan voted for Spider-Verse
  { id: 5, movieNightId: 2, movieChoiceId: 4, userId: 3 }, // Sam voted for Spirited Away
  { id: 6, movieNightId: 3, movieChoiceId: 7, userId: 1 }, // Alex voted for Inception
];

export default function App() {
  // Navigation tabs: 'demo' | 'code' | 'docs'
  const [activeTab, setActiveTab] = useState<'demo' | 'code' | 'docs'>('demo');

  // Application State
  const [currentUser, setCurrentUser] = useState<UserAccount | null>(DEMO_USERS[0]); // Default to Alex
  const [movieNights, setMovieNights] = useState<MovieNight[]>(INITIAL_NIGHTS);
  const [choices, setChoices] = useState<MovieChoice[]>(INITIAL_CHOICES);
  const [votes, setVotes] = useState<Vote[]>(INITIAL_VOTES);

  // Demo Page Navigation State
  const [selectedNightId, setSelectedNightId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');

  // Modals
  const [trailerModal, setTrailerModal] = useState<{ isOpen: boolean; title: string; embedUrl: string }>({
    isOpen: false,
    title: '',
    embedUrl: '',
  });
  const [isFinalizeModalOpen, setIsFinalizeModalOpen] = useState(false);
  const [selectedWinnerId, setSelectedWinnerId] = useState<number | null>(null);
  const [isAddChoiceModalOpen, setIsAddChoiceModalOpen] = useState(false);
  const [isCreateNightModalOpen, setIsCreateNightModalOpen] = useState(false);
  const [isEditNightModalOpen, setIsEditNightModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'info' | 'warning' } | null>(null);

  // New Choice Form State
  const [newChoiceForm, setNewChoiceForm] = useState({
    title: '',
    genre: '',
    reason: '',
    posterUrl: '',
    trailerUrl: '',
  });

  // New Night Form State
  const [newNightForm, setNewNightForm] = useState({
    title: '',
    date: '2026-11-15',
    category: 'Comedy' as 'Comedy' | 'Action' | 'Animation' | 'Other',
    description: '',
  });

  // Edit Night Form State
  const [editNightForm, setEditNightForm] = useState({
    title: '',
    date: '',
    category: 'Comedy' as 'Comedy' | 'Action' | 'Animation' | 'Other',
    description: '',
  });

  // Code Explorer State
  const fileKeys = useMemo(() => Object.keys(PROJECT_FILES), []);
  const [activeFile, setActiveFile] = useState<string>('app.py');
  const [copiedFile, setCopiedFile] = useState(false);

  // Toast Helper
  const showToast = (text: string, type: 'success' | 'info' | 'warning' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => {
      setToastMessage(null);
    }, 4500);
  };

  // YouTube Embed Extractor Helper
  const extractEmbedUrl = (url: string) => {
    if (!url) return '';
    try {
      if (url.includes('youtu.be/')) {
        const id = url.split('youtu.be/')[1]?.split('?')[0];
        return `https://www.youtube-nocookie.com/embed/${id}?rel=0`;
      }
      if (url.includes('youtube.com/watch')) {
        const urlObj = new URL(url);
        const id = urlObj.searchParams.get('v');
        return `https://www.youtube-nocookie.com/embed/${id}?rel=0`;
      }
      if (url.includes('youtube.com/embed/')) {
        return url;
      }
    } catch {
      return '';
    }
    return '';
  };

  // Voting Handler
  const handleVote = (nightId: number, choiceId: number) => {
    if (!currentUser) {
      showToast('Please select a user account to cast a vote.', 'warning');
      return;
    }

    const night = movieNights.find((n) => n.id === nightId);
    if (!night || night.status === 'finalized') {
      showToast('Voting is closed for this movie night.', 'warning');
      return;
    }

    // Check if user already voted in this night
    const existingVoteIndex = votes.findIndex(
      (v) => v.movieNightId === nightId && v.userId === currentUser.id
    );

    const choice = choices.find((c) => c.id === choiceId);
    const movieTitle = choice?.title || 'Selected movie';

    if (existingVoteIndex >= 0) {
      if (votes[existingVoteIndex].movieChoiceId === choiceId) {
        showToast(`You have already voted for "${movieTitle}".`, 'info');
        return;
      }
      // Update existing vote (simulating ON DUPLICATE KEY UPDATE)
      const updatedVotes = [...votes];
      updatedVotes[existingVoteIndex] = {
        ...updatedVotes[existingVoteIndex],
        movieChoiceId: choiceId,
      };
      setVotes(updatedVotes);
      showToast(`Switched your vote to "${movieTitle}"!`, 'success');
    } else {
      // Create new vote
      const newVote: Vote = {
        id: Date.now(),
        movieNightId: nightId,
        movieChoiceId: choiceId,
        userId: currentUser.id,
      };
      setVotes([...votes, newVote]);
      showToast(`Recorded your vote for "${movieTitle}"!`, 'success');
    }
  };

  // Finalize Handler
  const handleFinalize = (nightId: number) => {
    if (!currentUser) return;
    const night = movieNights.find((n) => n.id === nightId);
    if (!night || night.creatorId !== currentUser.id) {
      showToast('Only the organizer can finalize this movie night.', 'warning');
      return;
    }

    const nightChoices = choices.filter((c) => c.movieNightId === nightId);
    if (nightChoices.length < 2) {
      showToast('You must add at least two movie choices before finalizing.', 'warning');
      return;
    }

    if (!selectedWinnerId) {
      showToast('Please choose a winning movie.', 'warning');
      return;
    }

    const winningMovie = choices.find((c) => c.id === selectedWinnerId);

    setMovieNights(
      movieNights.map((n) =>
        n.id === nightId
          ? { ...n, status: 'finalized', finalMovieId: selectedWinnerId }
          : n
      )
    );
    setIsFinalizeModalOpen(false);
    showToast(
      `Movie night finalized! The winner is "${winningMovie?.title}". Voting is now closed.`,
      'success'
    );
  };

  // Add Choice Handler
  const handleAddChoice = (nightId: number) => {
    if (!currentUser) return;
    if (!newChoiceForm.title || !newChoiceForm.genre || !newChoiceForm.reason || !newChoiceForm.posterUrl) {
      showToast('Please fill in title, genre, reason, and poster URL.', 'warning');
      return;
    }

    const newChoice: MovieChoice = {
      id: Date.now(),
      movieNightId: nightId,
      title: newChoiceForm.title,
      genre: newChoiceForm.genre,
      reason: newChoiceForm.reason,
      posterUrl: newChoiceForm.posterUrl,
      trailerUrl: newChoiceForm.trailerUrl || undefined,
      trailerEmbedUrl: extractEmbedUrl(newChoiceForm.trailerUrl),
    };

    setChoices([...choices, newChoice]);
    setNewChoiceForm({ title: '', genre: '', reason: '', posterUrl: '', trailerUrl: '' });
    setIsAddChoiceModalOpen(false);
    showToast(`Added "${newChoice.title}" to movie suggestions!`, 'success');
  };

  // Delete Choice Handler
  const handleDeleteChoice = (choiceId: number) => {
    const choice = choices.find((c) => c.id === choiceId);
    if (!confirm(`Are you sure you want to remove "${choice?.title}"?`)) return;

    setChoices(choices.filter((c) => c.id !== choiceId));
    setVotes(votes.filter((v) => v.movieChoiceId !== choiceId));
    showToast(`Removed "${choice?.title}".`, 'info');
  };

  // Create Movie Night Handler
  const handleCreateNight = () => {
    if (!currentUser) {
      showToast('Please log in to create a movie night.', 'warning');
      return;
    }
    if (!newNightForm.title || !newNightForm.date || !newNightForm.description) {
      showToast('Please fill in all movie night details.', 'warning');
      return;
    }

    const newNight: MovieNight = {
      id: Date.now(),
      creatorId: currentUser.id,
      creatorName: currentUser.name,
      creatorUsername: currentUser.username,
      title: newNightForm.title,
      date: newNightForm.date,
      category: newNightForm.category,
      description: newNightForm.description,
      status: 'open',
      finalMovieId: null,
    };

    setMovieNights([newNight, ...movieNights]);
    setIsCreateNightModalOpen(false);
    setSelectedNightId(newNight.id);
    setNewNightForm({ title: '', date: '2026-11-15', category: 'Comedy', description: '' });
    showToast('Movie night created! Suggest movie choices below.', 'success');
  };

  // Edit Movie Night Handler
  const handleSaveEditNight = () => {
    if (!selectedNightId || !currentUser) return;
    setMovieNights(
      movieNights.map((n) =>
        n.id === selectedNightId
          ? {
              ...n,
              title: editNightForm.title,
              date: editNightForm.date,
              category: editNightForm.category,
              description: editNightForm.description,
            }
          : n
      )
    );
    setIsEditNightModalOpen(false);
    showToast('Movie night details updated!', 'success');
  };

  // Delete Movie Night Handler
  const handleDeleteNight = (nightId: number) => {
    const night = movieNights.find((n) => n.id === nightId);
    if (!confirm(`Are you sure you want to delete "${night?.title}"? This cannot be undone.`)) return;

    setMovieNights(movieNights.filter((n) => n.id !== nightId));
    setChoices(choices.filter((c) => c.movieNightId !== nightId));
    setVotes(votes.filter((v) => v.movieNightId !== nightId));
    setSelectedNightId(null);
    showToast(`Deleted movie night "${night?.title}".`, 'info');
  };

  // Filtered Movie Nights for Home View
  const filteredNights = useMemo(() => {
    return movieNights.filter((night) => {
      const matchesSearch =
        !searchQuery ||
        night.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        night.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        !selectedCategory || night.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [movieNights, searchQuery, selectedCategory]);

  // Current Selected Movie Night Details
  const currentNight = useMemo(
    () => (selectedNightId ? movieNights.find((n) => n.id === selectedNightId) : null),
    [movieNights, selectedNightId]
  );

  const currentChoices = useMemo(() => {
    if (!selectedNightId) return [];
    const nightChoices = choices.filter((c) => c.movieNightId === selectedNightId);
    const nightVotes = votes.filter((v) => v.movieNightId === selectedNightId);
    const totalVotes = nightVotes.length;

    return nightChoices.map((choice) => {
      const choiceVotes = nightVotes.filter((v) => v.movieChoiceId === choice.id).length;
      const percentage = totalVotes > 0 ? Math.round((choiceVotes / totalVotes) * 100) : 0;
      return {
        ...choice,
        voteCount: choiceVotes,
        percentage,
      };
    });
  }, [choices, votes, selectedNightId]);

  const userVotedChoiceId = useMemo(() => {
    if (!currentUser || !selectedNightId) return null;
    const userVote = votes.find(
      (v) => v.movieNightId === selectedNightId && v.userId === currentUser.id
    );
    return userVote ? userVote.movieChoiceId : null;
  }, [votes, currentUser, selectedNightId]);

  const finalWinningChoice = useMemo(() => {
    if (!currentNight || !currentNight.finalMovieId) return null;
    return currentChoices.find((c) => c.id === currentNight.finalMovieId);
  }, [currentNight, currentChoices]);

  // Copy Code Handler
  const handleCopyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFile(true);
    setTimeout(() => setCopiedFile(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 animate-bounce">
          <div
            className={`px-4 py-3 rounded-xl shadow-2xl border flex items-center gap-3 ${
              toastMessage.type === 'success'
                ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/50'
                : toastMessage.type === 'warning'
                ? 'bg-amber-950/90 text-amber-200 border-amber-500/50'
                : 'bg-blue-950/90 text-blue-200 border-blue-500/50'
            }`}
          >
            {toastMessage.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <Sparkles className="w-5 h-5 text-amber-400" />
            )}
            <span className="text-sm font-medium">{toastMessage.text}</span>
          </div>
        </div>
      )}

      {/* Top Application Navbar */}
      <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-rose-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Film className="w-5 h-5 text-slate-950 font-bold" />
            </div>
            <div>
              <span className="text-lg font-extrabold tracking-tight text-white">
                MovieNight<span className="text-amber-400">.Planner</span>
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs text-slate-400 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700">
                Flask + MySQL Project
              </span>
            </div>
          </div>

          {/* Navigation Mode Selector */}
          <div className="flex items-center gap-1 sm:gap-2 p-1 rounded-xl bg-slate-950 border border-slate-800">
            <button
              onClick={() => setActiveTab('demo')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'demo'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Play className="w-4 h-4" />
              <span>Live Preview</span>
            </button>
            <button
              onClick={() => setActiveTab('code')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'code'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Code className="w-4 h-4" />
              <span>Project Files ({fileKeys.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('docs')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'docs'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              <span>Setup &amp; Viva</span>
            </button>
          </div>

          {/* Download ZIP CTA */}
          <div className="flex items-center gap-2">
            <a
              href="/movie_night_planner.zip"
              download="movie_night_planner.zip"
              className="hidden md:inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold bg-slate-800 hover:bg-slate-700 text-amber-400 border border-amber-500/30 transition-all hover:scale-105"
            >
              <Download className="w-4 h-4" />
              <span>Download ZIP</span>
            </a>
          </div>
        </div>
      </header>

      {/* Subheader: User Account Switcher (For testing Flask sessions & roles) */}
      <div className="bg-slate-900 border-b border-slate-800/80 px-4 py-2.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-slate-300">Simulate Flask Session User:</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {DEMO_USERS.map((user) => {
              const isSelected = currentUser?.id === user.id;
              return (
                <button
                  key={user.id}
                  onClick={() => {
                    setCurrentUser(user);
                    showToast(`Logged in as @${user.username} (${user.name})`, 'info');
                  }}
                  className={`px-2.5 py-1 rounded-full font-medium transition-all flex items-center gap-1.5 ${
                    isSelected
                      ? 'bg-amber-400 text-slate-950 font-bold shadow-sm'
                      : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <User className="w-3.5 h-3.5" />
                  <span>{user.name}</span>
                  <span className="text-[10px] opacity-75">(@{user.username})</span>
                </button>
              );
            })}
            <button
              onClick={() => {
                setCurrentUser(null);
                showToast('Logged out. Browsing as Guest.', 'info');
              }}
              className={`px-2.5 py-1 rounded-full font-medium transition-all ${
                currentUser === null
                  ? 'bg-rose-500 text-white font-bold'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              Guest (Logged Out)
            </button>
          </div>
        </div>
      </div>

      {/* MAIN VIEW AREA */}
      <div className="flex-1">
        {/* ============================================================== */}
        {/* TAB 1: LIVE INTERACTIVE APP DEMO (SIMULATES FLASK + BOOTSTRAP) */}
        {/* ============================================================== */}
        {activeTab === 'demo' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            {/* If a Movie Night is selected -> Show Detail View */}
            {selectedNightId && currentNight ? (
              <div>
                {/* Back Link */}
                <div className="mb-4">
                  <button
                    onClick={() => setSelectedNightId(null)}
                    className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-amber-400 transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    <span>Back to All Movie Nights</span>
                  </button>
                </div>

                {/* Movie Night Header Card */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-8 shadow-xl">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
                    <div className="space-y-3 flex-1">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
                          {currentNight.category}
                        </span>
                        {currentNight.status === 'finalized' ? (
                          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1.5">
                            <Trophy className="w-3.5 h-3.5 text-amber-400" />
                            Voting Closed &bull; Winner Selected
                          </span>
                        ) : (
                          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            Voting Open
                          </span>
                        )}
                      </div>

                      <h1 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
                        {currentNight.title}
                      </h1>

                      <div className="flex flex-wrap items-center gap-4 text-xs sm:text-sm text-slate-400">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-4 h-4 text-amber-400" />
                          <span>Date: <strong className="text-slate-200">{currentNight.date}</strong></span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <User className="w-4 h-4 text-amber-400" />
                          <span>Organizer: <strong className="text-slate-200">{currentNight.creatorName}</strong></span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <ThumbsUp className="w-4 h-4 text-amber-400" />
                          <span>Total Community Votes: <strong className="text-slate-200">{votes.filter(v => v.movieNightId === currentNight.id).length}</strong></span>
                        </div>
                      </div>

                      <p className="text-slate-300 text-sm leading-relaxed pt-2 max-w-3xl">
                        {currentNight.description}
                      </p>
                    </div>

                    {/* Organizer Action Buttons (Only visible to Creator) */}
                    {currentUser && currentUser.id === currentNight.creatorId && (
                      <div className="flex flex-wrap md:flex-col gap-2 shrink-0">
                        {currentNight.status === 'open' && (
                          <>
                            <button
                              onClick={() => {
                                setEditNightForm({
                                  title: currentNight.title,
                                  date: currentNight.date,
                                  category: currentNight.category,
                                  description: currentNight.description,
                                });
                                setIsEditNightModalOpen(true);
                              }}
                              className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-all"
                            >
                              <Edit3 className="w-4 h-4" />
                              <span>Edit Details</span>
                            </button>

                            {currentChoices.length >= 2 && (
                              <button
                                onClick={() => {
                                  setSelectedWinnerId(currentChoices[0]?.id || null);
                                  setIsFinalizeModalOpen(true);
                                }}
                                className="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 flex items-center gap-1.5 shadow-lg shadow-amber-500/20 transition-all"
                              >
                                <Trophy className="w-4 h-4" />
                                <span>Finalize Winner</span>
                              </button>
                            )}
                          </>
                        )}
                        <button
                          onClick={() => handleDeleteNight(currentNight.id)}
                          className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 flex items-center gap-1.5 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                          <span>Delete Night</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Prominent Winning Movie Showcase (If Finalized) */}
                {currentNight.status === 'finalized' && finalWinningChoice && (
                  <div className="bg-gradient-to-br from-slate-900 via-amber-950/20 to-slate-900 border-2 border-amber-500/70 rounded-3xl p-6 sm:p-8 mb-10 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 transform translate-x-8 -translate-y-8 w-40 h-40 bg-amber-500/10 rounded-full blur-2xl"></div>

                    <div className="flex flex-col lg:flex-row items-center gap-6">
                      {/* Winner Poster */}
                      <div className="w-48 sm:w-56 shrink-0 aspect-[2/3] rounded-2xl overflow-hidden shadow-2xl border-2 border-amber-500/40 bg-slate-950">
                        <img
                          src={finalWinningChoice.posterUrl}
                          alt={finalWinningChoice.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = '/images/movie-placeholder.svg';
                          }}
                        />
                      </div>

                      {/* Winner Info */}
                      <div className="flex-1 text-center lg:text-left space-y-3">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 text-xs font-extrabold tracking-wide uppercase shadow-md">
                          <Award className="w-4 h-4" />
                          <span>Official Winning Selection</span>
                        </div>

                        <h2 className="text-2xl sm:text-4xl font-extrabold text-white">
                          {finalWinningChoice.title}
                        </h2>

                        <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2">
                          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                            {finalWinningChoice.genre}
                          </span>
                          <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-400 text-slate-950">
                            {finalWinningChoice.voteCount} Votes Won
                          </span>
                        </div>

                        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 text-left max-w-2xl">
                          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                            Organizer's Recommendation:
                          </span>
                          <p className="text-slate-200 text-sm leading-relaxed">
                            {finalWinningChoice.reason}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3 pt-2">
                          {finalWinningChoice.trailerEmbedUrl && (
                            <button
                              onClick={() =>
                                setTrailerModal({
                                  isOpen: true,
                                  title: finalWinningChoice.title,
                                  embedUrl: finalWinningChoice.trailerEmbedUrl!,
                                })
                              }
                              className="px-5 py-2.5 rounded-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-sm flex items-center gap-2 shadow-lg shadow-amber-500/20 transition-transform active:scale-95"
                            >
                              <Play className="w-4 h-4 fill-slate-950" />
                              <span>Watch Official Trailer</span>
                            </button>
                          )}
                          <div className="text-xs text-slate-400 flex items-center gap-1.5 py-1">
                            <Lock className="w-3.5 h-3.5 text-amber-400" />
                            <span>Voting is concluded. Enjoy the movie night!</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Movie Choices Header & Add Choice Trigger */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
                      <Film className="w-5 h-5 text-amber-400" />
                      <span>Movie Suggestions</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
                        {currentChoices.length}
                      </span>
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-400">
                      {currentNight.status === 'open'
                        ? 'Vote for your favorite film below. You can change your vote anytime before finalization.'
                        : 'Voting has concluded for this event.'}
                    </p>
                  </div>

                  {currentUser && currentUser.id === currentNight.creatorId && currentNight.status === 'open' && (
                    <button
                      onClick={() => setIsAddChoiceModalOpen(true)}
                      className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs sm:text-sm font-bold flex items-center gap-1.5 shadow-md shadow-amber-500/20 transition-all"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Suggest a Movie</span>
                    </button>
                  )}
                </div>

                {/* Movie Choices Grid */}
                {currentChoices.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    {currentChoices.map((choice) => {
                      const isVotedByMe = userVotedChoiceId === choice.id;
                      const isWinner = choice.id === currentNight.finalMovieId;

                      return (
                        <div
                          key={choice.id}
                          className={`bg-slate-900 rounded-2xl overflow-hidden border flex flex-col transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl ${
                            isWinner
                              ? 'border-amber-500 ring-2 ring-amber-500/30'
                              : isVotedByMe
                              ? 'border-emerald-500/80 ring-1 ring-emerald-500/20'
                              : 'border-slate-800'
                          }`}
                        >
                          {/* Movie Poster (2:3 aspect ratio) */}
                          <div className="relative aspect-[2/3] w-full bg-slate-950 overflow-hidden">
                            <img
                              src={choice.posterUrl}
                              alt={choice.title}
                              className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = '/images/movie-placeholder.svg';
                              }}
                            />

                            {/* Status Ribbons */}
                            {isWinner && (
                              <div className="absolute top-3 left-3 bg-amber-500 text-slate-950 font-black text-xs px-2.5 py-1 rounded-full shadow-lg flex items-center gap-1">
                                <Trophy className="w-3.5 h-3.5" />
                                <span>WINNER</span>
                              </div>
                            )}

                            {isVotedByMe && (
                              <div className="absolute top-3 right-3 bg-emerald-500 text-white font-bold text-xs px-2.5 py-1 rounded-full shadow-lg flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Your Pick</span>
                              </div>
                            )}
                          </div>

                          {/* Card Content */}
                          <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                            <div>
                              <div className="flex items-start justify-between gap-2 mb-1.5">
                                <h3 className="font-bold text-lg text-white line-clamp-1" title={choice.title}>
                                  {choice.title}
                                </h3>
                              </div>

                              <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 mb-3 border border-slate-700">
                                {choice.genre}
                              </span>

                              <p className="text-slate-400 text-xs sm:text-sm line-clamp-3 leading-relaxed mb-4">
                                <strong className="text-slate-300">Why watch:</strong> {choice.reason}
                              </p>
                            </div>

                            {/* Vote Progress Bar */}
                            <div className="space-y-1.5">
                              <div className="flex justify-between items-center text-xs text-slate-400">
                                <span className="font-semibold text-slate-300">Community Votes</span>
                                <span className="font-bold text-amber-400">
                                  {choice.voteCount} ({choice.percentage}%)
                                </span>
                              </div>
                              <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                                <div
                                  className="h-full bg-gradient-to-r from-amber-500 to-rose-500 rounded-full transition-all duration-500"
                                  style={{ width: `${choice.percentage}%` }}
                                ></div>
                              </div>
                            </div>

                            {/* Watch Trailer Button */}
                            {choice.trailerEmbedUrl && (
                              <button
                                onClick={() =>
                                  setTrailerModal({
                                    isOpen: true,
                                    title: choice.title,
                                    embedUrl: choice.trailerEmbedUrl!,
                                  })
                                }
                                className="w-full py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 flex items-center justify-center gap-1.5 transition-colors"
                              >
                                <Play className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                                <span>Watch Trailer</span>
                              </button>
                            )}

                            {/* Action Buttons: Vote / Switch Vote / Delete */}
                            <div className="pt-3 border-t border-slate-800 flex items-center gap-2">
                              {currentNight.status === 'open' ? (
                                currentUser ? (
                                  <button
                                    onClick={() => handleVote(currentNight.id, choice.id)}
                                    className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                                      isVotedByMe
                                        ? 'bg-emerald-600 text-white cursor-default shadow-md'
                                        : userVotedChoiceId
                                        ? 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/40'
                                        : 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/10'
                                    }`}
                                  >
                                    {isVotedByMe ? (
                                      <>
                                        <Check className="w-3.5 h-3.5" />
                                        <span>Current Vote</span>
                                      </>
                                    ) : userVotedChoiceId ? (
                                      <>
                                        <RotateCcw className="w-3.5 h-3.5" />
                                        <span>Switch Vote</span>
                                      </>
                                    ) : (
                                      <>
                                        <ThumbsUp className="w-3.5 h-3.5" />
                                        <span>Vote</span>
                                      </>
                                    )}
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => showToast('Please select a user above to vote!', 'warning')}
                                    className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-slate-800 text-slate-400 hover:bg-slate-750 transition-colors"
                                  >
                                    Log in to vote
                                  </button>
                                )
                              ) : (
                                <button
                                  disabled
                                  className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-slate-800/60 text-slate-500 cursor-not-allowed flex items-center justify-center gap-1.5"
                                >
                                  <Lock className="w-3.5 h-3.5" />
                                  <span>Voting Closed</span>
                                </button>
                              )}

                              {/* Creator delete choice button */}
                              {currentUser && currentUser.id === currentNight.creatorId && currentNight.status === 'open' && (
                                <button
                                  onClick={() => handleDeleteChoice(choice.id)}
                                  className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 border border-transparent hover:border-rose-900/50 transition-colors"
                                  title="Remove Choice"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
                    <Film className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <h3 className="text-lg font-bold text-white mb-1">No Movie Suggestions Yet</h3>
                    <p className="text-sm text-slate-400 max-w-md mx-auto mb-5">
                      {currentUser?.id === currentNight.creatorId
                        ? 'As the organizer, add at least two movie suggestions so friends can start voting!'
                        : 'The organizer has not added choices yet. Check back soon to cast your vote!'}
                    </p>
                    {currentUser?.id === currentNight.creatorId && currentNight.status === 'open' && (
                      <button
                        onClick={() => setIsAddChoiceModalOpen(true)}
                        className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs sm:text-sm inline-flex items-center gap-2 shadow-md shadow-amber-500/20"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Add First Movie Suggestion</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              /* Home / Browse Movie Nights View */
              <div>
                {/* Hero Section */}
                <div className="relative rounded-3xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 p-8 sm:p-12 text-center mb-8 shadow-2xl overflow-hidden">
                  <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-bold mb-4">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Flask &bull; MySQL &bull; Bootstrap 5.3.8 Web Application</span>
                  </div>

                  <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight mb-4 max-w-3xl mx-auto">
                    Vote. Decide. Watch Together.
                  </h1>

                  <p className="text-slate-400 text-sm sm:text-base max-w-2xl mx-auto mb-6">
                    A cinematic web app where registered friends can organize movie nights, suggest titles with real posters and trailers, vote fairly, and finalize the winning film.
                  </p>

                  <div className="flex flex-wrap items-center justify-center gap-3">
                    {currentUser ? (
                      <button
                        onClick={() => setIsCreateNightModalOpen(true)}
                        className="px-6 py-3 rounded-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold text-sm flex items-center gap-2 shadow-lg shadow-amber-500/25 transition-transform active:scale-95"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Host a Movie Night</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => {
                          setCurrentUser(DEMO_USERS[0]);
                          showToast('Signed in as Alex Rivera!', 'success');
                        }}
                        className="px-6 py-3 rounded-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold text-sm flex items-center gap-2 shadow-lg shadow-amber-500/25 transition-transform active:scale-95"
                      >
                        <User className="w-4 h-4" />
                        <span>Sign In as Demo User</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Search & Filter Toolbar */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 mb-8 shadow-lg">
                  <div className="flex flex-col md:flex-row items-stretch md:items-center gap-4">
                    {/* Search Input */}
                    <div className="flex-1 relative">
                      <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search movie nights by title or description..."
                        className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 text-sm focus:outline-none focus:border-amber-500 transition-colors"
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery('')}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>

                    {/* Category Filter Chips */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {['', 'Comedy', 'Action', 'Animation', 'Other'].map((cat) => {
                        const isSelected = selectedCategory === cat;
                        return (
                          <button
                            key={cat || 'All'}
                            onClick={() => setSelectedCategory(cat)}
                            className={`px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                              isSelected
                                ? 'bg-amber-500 text-slate-950 font-bold shadow-md shadow-amber-500/20'
                                : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                            }`}
                          >
                            {cat || 'All Categories'}
                          </button>
                        );
                      })}
                    </div>

                    {/* Clear Filters */}
                    {(searchQuery || selectedCategory) && (
                      <button
                        onClick={() => {
                          setSearchQuery('');
                          setSelectedCategory('');
                        }}
                        className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 flex items-center justify-center gap-1"
                        title="Reset Filters"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Reset</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Movie Nights Grid Header */}
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg sm:text-xl font-bold text-white flex items-center gap-2">
                    <Film className="w-5 h-5 text-amber-400" />
                    <span>Available Movie Nights</span>
                    <span className="px-2 py-0.5 rounded-full text-xs bg-slate-800 text-slate-400">
                      {filteredNights.length}
                    </span>
                  </h2>

                  {currentUser && (
                    <button
                      onClick={() => setIsCreateNightModalOpen(true)}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 border border-amber-500/30 text-xs font-bold flex items-center gap-1.5 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Plan Night</span>
                    </button>
                  )}
                </div>

                {/* Movie Nights List */}
                {filteredNights.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredNights.map((night) => {
                      const nightChoices = choices.filter((c) => c.movieNightId === night.id);
                      const nightVotes = votes.filter((v) => v.movieNightId === night.id);
                      const winnerChoice = nightChoices.find((c) => c.id === night.finalMovieId);

                      return (
                        <div
                          key={night.id}
                          className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 sm:p-6 flex flex-col justify-between transition-all duration-200 hover:-translate-y-1 hover:shadow-xl group"
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
                                {night.category}
                              </span>
                              {night.status === 'finalized' ? (
                                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                                  <Trophy className="w-3 h-3 text-amber-400" />
                                  Finalized
                                </span>
                              ) : (
                                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                  Voting Open
                                </span>
                              )}
                            </div>

                            <h3
                              onClick={() => setSelectedNightId(night.id)}
                              className="text-lg font-bold text-white group-hover:text-amber-400 transition-colors cursor-pointer"
                            >
                              {night.title}
                            </h3>

                            <div className="space-y-1 text-xs text-slate-400">
                              <div className="flex items-center gap-1.5">
                                <Calendar className="w-3.5 h-3.5 text-amber-400" />
                                <span>Event Date: <strong className="text-slate-300">{night.date}</strong></span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <User className="w-3.5 h-3.5 text-amber-400" />
                                <span>Host: <span className="text-slate-300">{night.creatorName}</span></span>
                              </div>
                            </div>

                            <p className="text-slate-400 text-xs line-clamp-3 leading-relaxed">
                              {night.description}
                            </p>

                            {/* Finalized Winner Callout */}
                            {night.status === 'finalized' && winnerChoice && (
                              <div className="p-2.5 rounded-xl bg-slate-950 border border-amber-500/40 flex items-center gap-2.5">
                                <Award className="w-5 h-5 text-amber-400 shrink-0" />
                                <div className="text-xs truncate">
                                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Winning Movie:</span>
                                  <strong className="text-amber-300 truncate block">{winnerChoice.title}</strong>
                                </div>
                              </div>
                            )}
                          </div>

                          <div className="pt-4 mt-4 border-t border-slate-800 flex items-center justify-between">
                            <span className="text-xs text-slate-400">
                              {nightChoices.length} movie choice{nightChoices.length !== 1 ? 's' : ''} &bull; {nightVotes.length} votes
                            </span>
                            <button
                              onClick={() => setSelectedNightId(night.id)}
                              className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-slate-800 group-hover:bg-amber-500 group-hover:text-slate-950 text-slate-200 transition-all"
                            >
                              View Details &rarr;
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
                    <Film className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <h3 className="text-lg font-bold text-white mb-1">No Movie Nights Match Your Filter</h3>
                    <p className="text-sm text-slate-400 max-w-md mx-auto mb-4">
                      Try clearing your search query or selecting "All Categories" to see all planned events.
                    </p>
                    <button
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedCategory('');
                      }}
                      className="px-4 py-2 rounded-xl bg-slate-800 text-slate-200 text-xs font-bold hover:bg-slate-700"
                    >
                      Clear Filters
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: PROJECT SOURCE CODE EXPLORER */}
        {/* ============================================================== */}
        {activeTab === 'code' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col md:flex-row min-h-[680px]">
              {/* File Tree Sidebar */}
              <div className="w-full md:w-72 bg-slate-950 border-r border-slate-800 p-4 shrink-0 flex flex-col">
                <div className="flex items-center justify-between mb-3 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-amber-400" />
                    <span className="font-bold text-sm text-white">Project Files</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
                    {fileKeys.length} files
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-1 text-xs">
                  {fileKeys.map((file) => {
                    const isSelected = activeFile === file;
                    return (
                      <button
                        key={file}
                        onClick={() => setActiveFile(file)}
                        className={`w-full text-left px-3 py-2 rounded-lg font-mono transition-all flex items-center justify-between ${
                          isSelected
                            ? 'bg-amber-500 text-slate-950 font-bold shadow-sm'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        <span className="truncate">{file}</span>
                        {file.endsWith('.py') && <span className="text-[10px] opacity-75 font-sans">Python</span>}
                        {file.endsWith('.html') && <span className="text-[10px] opacity-75 font-sans">Jinja</span>}
                        {file.endsWith('.sql') && <span className="text-[10px] opacity-75 font-sans">SQL</span>}
                      </button>
                    );
                  })}
                </div>

                <div className="pt-4 mt-3 border-t border-slate-800">
                  <a
                    href="/movie_night_planner.zip"
                    download="movie_night_planner.zip"
                    className="w-full py-2.5 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md shadow-amber-500/20"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Project ZIP</span>
                  </a>
                </div>
              </div>

              {/* Code Viewer */}
              <div className="flex-1 flex flex-col bg-slate-900 overflow-hidden">
                <div className="bg-slate-950/80 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2 font-mono text-xs text-slate-300">
                    <Code className="w-4 h-4 text-amber-400" />
                    <span>movie_night_planner/{activeFile}</span>
                  </div>

                  <button
                    onClick={() => handleCopyCode(PROJECT_FILES[activeFile] || '')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors border border-slate-700"
                  >
                    {copiedFile ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy File</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="flex-1 p-4 overflow-auto font-mono text-xs leading-relaxed text-slate-300 bg-slate-950 select-text">
                  <pre className="overflow-x-auto whitespace-pre">
                    {PROJECT_FILES[activeFile] || '// File content not available'}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: WINDOWS & MYSQL SETUP + VIVA EVALUATION GUIDE */}
        {/* ============================================================== */}
        {activeTab === 'docs' && (
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
            {/* Guide Header */}
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
                  <Terminal className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white">Installation &amp; Demonstration Guide</h1>
                  <p className="text-xs text-slate-400">Everything needed to run the Flask + MySQL app locally and ace your college project review.</p>
                </div>
              </div>
            </div>

            {/* Step-by-Step Installation Commands */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Windows PowerShell */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-amber-400" />
                  <span>1. Windows Setup (PowerShell)</span>
                </h2>
                <div className="bg-slate-950 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-2 border border-slate-800 overflow-x-auto">
                  <p className="text-slate-500"># Navigate to project</p>
                  <p className="text-amber-300">cd movie_night_planner</p>
                  <p className="text-slate-500"># Create virtual environment</p>
                  <p className="text-amber-300">python -m venv venv</p>
                  <p className="text-slate-500"># Activate environment</p>
                  <p className="text-amber-300">.\venv\Scripts\Activate.ps1</p>
                  <p className="text-slate-500"># Install dependencies</p>
                  <p className="text-amber-300">pip install -r requirements.txt</p>
                  <p className="text-slate-500"># Run Flask app</p>
                  <p className="text-emerald-400">python app.py</p>
                </div>
              </div>

              {/* MySQL Setup */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-amber-400" />
                  <span>2. MySQL Database Setup</span>
                </h2>
                <div className="bg-slate-950 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-2 border border-slate-800 overflow-x-auto">
                  <p className="text-slate-500"># Log in to MySQL client</p>
                  <p className="text-amber-300">mysql -u root -p</p>
                  <p className="text-slate-500"># Create database</p>
                  <p className="text-amber-300">CREATE DATABASE movie_night_planner;</p>
                  <p className="text-amber-300">EXIT;</p>
                  <p className="text-slate-500"># Note: Tables and seed data are created automatically by app.py on startup!</p>
                </div>
              </div>
            </div>

            {/* College Viva Questions & Answers */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-amber-400" />
                <h2 className="text-xl font-bold text-white">College Project Viva &amp; Architecture Q&amp;A</h2>
              </div>

              <div className="space-y-4">
                <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-1.5">
                  <h3 className="text-sm font-bold text-amber-400">Q1: How are passwords secured in the database?</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    We use <code>werkzeug.security.generate_password_hash</code>, which utilizes PBKDF2 with salted SHA-256 (or scrypt). Passwords are never stored in plain text. During login, <code>check_password_hash</code> compares the entered password against the salted hash without revealing the original plaintext.
                  </p>
                </div>

                <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-1.5">
                  <h3 className="text-sm font-bold text-amber-400">Q2: How does the application prevent duplicate voting?</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    In the <code>votes</code> table, we enforce a composite unique key: <code>CONSTRAINT uq_user_movie_night UNIQUE (movie_night_id, user_id)</code>. When a user casts a vote, our SQL query executes <code>INSERT INTO votes ... ON DUPLICATE KEY UPDATE movie_choice_id = VALUES(movie_choice_id)</code>. This allows a user to switch their choice seamlessly without ever inflating the voter count.
                  </p>
                </div>

                <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-1.5">
                  <h3 className="text-sm font-bold text-amber-400">Q3: How are SQL injection attacks prevented?</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    All queries are parameterized using <code>%s</code> placeholders handled directly by <code>mysql-connector-python</code>. User inputs are never directly concatenated into raw SQL strings, ensuring malicious input cannot manipulate SQL query syntax.
                  </p>
                </div>

                <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-1.5">
                  <h3 className="text-sm font-bold text-amber-400">Q4: How is server-side authorization handled?</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Rather than relying solely on hidden UI buttons, every mutating endpoint (editing a movie night, deleting an event, adding a choice, or finalizing the winner) fetches the record from MySQL and verifies <code>if night['creator_id'] != session['user_id']: abort(403)</code> before performing the transaction.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ============================================================== */}
      {/* MODAL: TRAILER PLAYER */}
      {/* ============================================================== */}
      {trailerModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-amber-400 fill-amber-400" />
                <h3 className="font-bold text-sm text-white">{trailerModal.title} - Official Trailer</h3>
              </div>
              <button
                onClick={() => setTrailerModal({ isOpen: false, title: '', embedUrl: '' })}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="aspect-video w-full bg-black">
              <iframe
                src={`${trailerModal.embedUrl}&autoplay=1`}
                title={`${trailerModal.title} Trailer`}
                className="w-full h-full border-0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              ></iframe>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: FINALIZE WINNER */}
      {/* ============================================================== */}
      {isFinalizeModalOpen && currentNight && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-amber-500/50 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400">
                <Trophy className="w-5 h-5" />
                <h3 className="font-bold text-base text-white">Finalize Winning Movie</h3>
              </div>
              <button
                onClick={() => setIsFinalizeModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              As the organizer, review the community vote counts and select the final film to watch. Once confirmed, voting will permanently lock!
            </p>

            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {currentChoices.map((choice) => (
                <label
                  key={choice.id}
                  className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                    selectedWinnerId === choice.id
                      ? 'bg-amber-500/10 border-amber-500 text-white'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="winnerChoice"
                      checked={selectedWinnerId === choice.id}
                      onChange={() => setSelectedWinnerId(choice.id)}
                      className="accent-amber-500"
                    />
                    <div>
                      <div className="font-bold text-xs">{choice.title}</div>
                      <div className="text-[11px] text-slate-400">{choice.genre}</div>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-amber-400 px-2 py-0.5 rounded-full bg-slate-900">
                    {choice.voteCount} votes
                  </span>
                </label>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsFinalizeModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={() => handleFinalize(currentNight.id)}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20"
              >
                Confirm Final Winner
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: ADD MOVIE CHOICE */}
      {/* ============================================================== */}
      {isAddChoiceModalOpen && currentNight && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Plus className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-base text-white">Suggest a Movie Choice</h3>
              </div>
              <button
                onClick={() => setIsAddChoiceModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Preset Buttons */}
            <div>
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
                Quick Fill Popular Choices:
              </span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() =>
                    setNewChoiceForm({
                      title: 'The Dark Knight',
                      genre: 'Action / Crime Thriller',
                      reason: 'Heath Ledger legendary Joker performance and intense Christopher Nolan directing.',
                      posterUrl: 'https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg',
                      trailerUrl: 'https://www.youtube.com/watch?v=EXeTwQWrcwY',
                    })
                  }
                  className="px-2.5 py-1 rounded-lg text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  The Dark Knight
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setNewChoiceForm({
                      title: 'Barbie',
                      genre: 'Comedy / Fantasy',
                      reason: 'Vibrant, hilarious, star-studded adventure by Greta Gerwig with catchy songs.',
                      posterUrl: 'https://image.tmdb.org/t/p/w500/iuFNMS8U5cb6xfzi51Dbkovj7vM.jpg',
                      trailerUrl: 'https://www.youtube.com/watch?v=pBk4NYhWNMM',
                    })
                  }
                  className="px-2.5 py-1 rounded-lg text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Barbie
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setNewChoiceForm({
                      title: 'Everything Everywhere All at Once',
                      genre: 'Action / Sci-Fi / Comedy',
                      reason: 'Multiverse masterpiece blending heart, martial arts comedy, and family reconciliation.',
                      posterUrl: 'https://image.tmdb.org/t/p/w500/w3LxiVYPqRLexP02LOV29bURul.jpg',
                      trailerUrl: 'https://www.youtube.com/watch?v=wxN1T1uxQ2g',
                    })
                  }
                  className="px-2.5 py-1 rounded-lg text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  EEAAO
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Movie Title *</label>
                <input
                  type="text"
                  value={newChoiceForm.title}
                  onChange={(e) => setNewChoiceForm({ ...newChoiceForm, title: e.target.value })}
                  placeholder="e.g. Inception"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Genre *</label>
                <input
                  type="text"
                  value={newChoiceForm.genre}
                  onChange={(e) => setNewChoiceForm({ ...newChoiceForm, genre: e.target.value })}
                  placeholder="e.g. Sci-Fi / Action"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Why should we watch this? *</label>
                <textarea
                  value={newChoiceForm.reason}
                  onChange={(e) => setNewChoiceForm({ ...newChoiceForm, reason: e.target.value })}
                  rows={2}
                  placeholder="Tell everyone why this fits the movie night..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Poster Image URL *</label>
                <input
                  type="url"
                  value={newChoiceForm.posterUrl}
                  onChange={(e) => setNewChoiceForm({ ...newChoiceForm, posterUrl: e.target.value })}
                  placeholder="https://image.tmdb.org/... or external poster link"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">YouTube Trailer Link (Optional)</label>
                <input
                  type="url"
                  value={newChoiceForm.trailerUrl}
                  onChange={(e) => setNewChoiceForm({ ...newChoiceForm, trailerUrl: e.target.value })}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsAddChoiceModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={() => handleAddChoice(currentNight.id)}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20"
              >
                Add Suggestion
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: CREATE MOVIE NIGHT */}
      {/* ============================================================== */}
      {isCreateNightModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-base text-white">Plan a New Movie Night</h3>
              </div>
              <button
                onClick={() => setIsCreateNightModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Movie Night Title *</label>
                <input
                  type="text"
                  value={newNightForm.title}
                  onChange={(e) => setNewNightForm({ ...newNightForm, title: e.target.value })}
                  placeholder="e.g. 90s Nostalgia Night"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Event Date *</label>
                  <input
                    type="date"
                    value={newNightForm.date}
                    onChange={(e) => setNewNightForm({ ...newNightForm, date: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Category *</label>
                  <select
                    value={newNightForm.category}
                    onChange={(e) => setNewNightForm({ ...newNightForm, category: e.target.value as any })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                  >
                    <option value="Comedy">Comedy</option>
                    <option value="Action">Action</option>
                    <option value="Animation">Animation</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Description &amp; Theme *</label>
                <textarea
                  value={newNightForm.description}
                  onChange={(e) => setNewNightForm({ ...newNightForm, description: e.target.value })}
                  rows={3}
                  placeholder="Describe the vibes, food, drinks, and plan..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsCreateNightModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateNight}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20"
              >
                Create Event
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: EDIT MOVIE NIGHT */}
      {/* ============================================================== */}
      {isEditNightModalOpen && currentNight && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-base text-white">Edit Movie Night Details</h3>
              </div>
              <button
                onClick={() => setIsEditNightModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Title *</label>
                <input
                  type="text"
                  value={editNightForm.title}
                  onChange={(e) => setEditNightForm({ ...editNightForm, title: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Event Date *</label>
                  <input
                    type="date"
                    value={editNightForm.date}
                    onChange={(e) => setEditNightForm({ ...editNightForm, date: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Category *</label>
                  <select
                    value={editNightForm.category}
                    onChange={(e) => setEditNightForm({ ...editNightForm, category: e.target.value as any })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                  >
                    <option value="Comedy">Comedy</option>
                    <option value="Action">Action</option>
                    <option value="Animation">Animation</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Description *</label>
                <textarea
                  value={editNightForm.description}
                  onChange={(e) => setEditNightForm({ ...editNightForm, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsEditNightModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEditNight}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-800 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-400">
            <Film className="w-4 h-4 text-amber-400" />
            <span className="font-bold text-slate-200">Movie Night Planner</span>
            <span>&bull; Python Flask &amp; MySQL Web Application</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab('code')}
              className="text-amber-400 hover:underline"
            >
              Browse Code Files
            </button>
            <button
              onClick={() => setActiveTab('docs')}
              className="text-amber-400 hover:underline"
            >
              Installation Guide
            </button>
            <a
              href="/movie_night_planner.zip"
              download="movie_night_planner.zip"
              className="text-amber-400 hover:underline font-bold"
            >
              Download ZIP
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
