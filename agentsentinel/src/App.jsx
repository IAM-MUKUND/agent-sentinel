import { useState } from 'react';
import Login from './components/Login';
import UserChat from './components/UserChat';
import AdminDashboard from './components/AdminDashboard';
import './App.css';

function App() {
  const [currentScreen, setCurrentScreen] = useState('login'); // 'login', 'user', 'admin'
  const [username, setUsername] = useState('');

  const handleLogin = (name, role) => {
    setUsername(name);
    if (role === 'admin') {
      setCurrentScreen('admin');
    } else {
      setCurrentScreen('user');
    }
  };

  const handleLogout = () => {
    setCurrentScreen('login');
    setUsername('');
  };

  return (
    <>
      {currentScreen === 'login' && <Login onLogin={handleLogin} />}
      {currentScreen === 'user' && <UserChat username={username} onLogout={handleLogout} />}
      {currentScreen === 'admin' && <AdminDashboard username={username} onLogout={handleLogout} />}
    </>
  );
}

export default App;
