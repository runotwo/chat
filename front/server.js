var express = require('express');

// создаём Express-приложение
var app = express();

// создаём маршрут для главной страницы
app.use(express.static('public'));
// http://localhost:8080/
app.get('/', function(req, res) {
  res.sendfile('index.html');
});
// запускаем сервер на порту 8080
app.listen(3000);
// отправляем сообщение
console.log('Сервер стартовал!');