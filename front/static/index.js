var app = new Vue({
    el: '#app',
    data: {
        login: '',
        pass: '',
        activity: 'log',
        username: '',
        chats: [],
        auth: false,
        errorLogin: '',
        errorPassword: '',
        current: '',
        message: '',
        sock: undefined
    },
    computed: {
        schats: function () {
            fdate = moment('00:52:15 01/01/1985', 'HH:mm:ss DD/MM/YYYY');
            mas = [];
            count = 0;
            for (key in this.chats) {
                mas[count] = {};
                $.extend(true, mas[count], this.chats[key]);
                mas[count].name = key;
                mas[count].lastMessage = mas[count].messages.length ? mas[count].messages[mas[count].messages.length - 1] : undefined;
                if (mas[count].lastMessage) {
                    if (mas[count].lastMessage.text.length + mas[count].lastMessage.sender.length > 45) {
                        mas[count].lastMessage.text = mas[count].lastMessage.text.slice(0, 45 - mas[count].lastMessage.sender.length);
                        mas[count].lastMessage.text += '...';
                    }
                }
                count++;
            }
            mas.sort(function (a, b) {
                if (a.messages.length) adate = moment(a.messages[a.messages.length - 1].time, 'HH:mm:ss DD/MM/YYYY');
                else adate = fdate;
                if (b.messages.length) bdate = moment(b.messages[b.messages.length - 1].time, 'HH:mm:ss DD/MM/YYYY');
                else bdate = fdate;
                if (adate > bdate) {
                    return -1;
                }
                if (adate < bdate) {
                    return 1;
                }
                return 0;
            });
            return mas;
        },
        currentMessages: function () {
            return this.chats[this.current].messages;
        }
    },
    methods: {

        register: function (e) {
            e.preventDefault();
            self = this;
            this.errorLogin = '';
            this.errorPassword = '';
            if (this.login.length < 3 || this.login.length > 10) {
                this.errorLogin = 'Login must be longer than 2 characters and shorter than 11';
            }
            else if (this.pass.length < 3 || this.pass.length > 10) {
                this.errorPassword = 'Password must be longer than 2 characters and shorter than 11';
            }
            else {
                axios.post('back:8000/registration', {
                    login: this.login,
                    password: this.pass,
                },)
                    .then(function (response) {
                        updateCookies(response);
                        if (response.data.result === 'ERR') {
                            self.errorLogin = 'Username already exists';
                        }
                        else {
                            self.activity = 'log';
                        }
                    })
                    .catch(function (error) {
                        console.log(error);
                    });
            }
            this.login = '';
            this.pass = '';
        },

        mlogin: function (e) {
            e.preventDefault();
            self = this;
            this.errorLogin = '';
            this.errorPassword = '';
            if (this.login.length < 3 || this.login.length > 10) {
                this.errorLogin = 'Login must be longer than 2 characters and shorter than 11';
            }
            else if (this.pass.length < 3 || this.pass.length > 10) {
                this.errorPassword = 'Password must be longer than 2 characters and shorter than 11';
            }
            else {
                axios.post('back:8000/login', {
                    login: this.login,
                    password: this.pass,
                },)
                    .then(function (response) {
                        updateCookies(response);
                        if (response.data.result === 'ERR') {
                            if (response.data.description === 'wrong password') {
                                self.errorPassword = 'Wrong password';
                            }
                            else self.errorLogin = 'Username not exists';
                        }
                    })
                    .catch(function (error) {
                        console.log(error);
                    })
                    .then(function () {
                        axios.get('back:8000', {
                            params: {
                                user: Vue.cookies.get('user')
                            }
                        })
                            .then(function (response) {
                                updateCookies(response);
                                if (response.data.auth) {
                                    conn(response);
                                }
                                else {
                                    disc();
                                }
                                console.log(response);
                            })
                            .catch(function (error) {
                                console.log(error);
                            });
                    });
            }
            this.login = '';
            this.pass = '';
        },

        logout: function () {
            self = this;
            Vue.cookies.remove('user');
            axios.get('back:8000', {
                params: {
                    user: Vue.cookies.get('user')
                }
            })
                .then(function (response) {
                    updateCookies(response);
                    if (response.data.auth) {
                        conn(response);
                    }
                    else {
                        disc()
                    }
                    console.log(response);
                })
                .catch(function (error) {
                    console.log(error);
                });
        },

        sendMessage: function (e) {
            e.preventDefault();
            if (this.message) {
                receiver = this.current;
                mess = {
                    act: 'message',
                    to: receiver,
                    text: this.message,
                    id: this.chats[this.current].messages.length
                };
                this.chats[receiver].messages.push({
                    sender: this.username,
                    text: this.message,
                    time: ''
                });
                this.sock.send(JSON.stringify(mess));
                this.message = '';
                this.$nextTick(function () {
                    updateScroll();
                });
            }
        },
        setCurrent: function (chat) {
            this.current = chat.name;
            this.message = '';
            this.chats[this.current].new = false;
            this.$nextTick(function () {
                updateScroll();
            });
        }

    },
    created: function () {
        self = this;
        axios.get('back:8000', {
            params: {
                user: Vue.cookies.get('user')
            }
        })
            .then(function (response) {
                updateCookies(response);
                if (response.data.auth) {
                    conn(response);
                }
                else {
                    disc();
                }
                console.log(response);
            })
            .catch(function (error) {
                console.log(error);
            });

    }
});


function updateCookies(response) {
    for (i in response.data.c) {
        Vue.cookies.remove(i);
        Vue.cookies.set(i, response.data.c[i]);
    }
}

function disc() {
    app.activity = 'log';
    app.auth = false;
    app.current = '';
    app.sock.close();
    app.sock = undefined;
    app.message = '';
}

function conn(response) {
    app.activity = 'auth';
    app.username = response.data.username;
    for (key in response.data.chats) {
        response.data.chats[key].new = false;
    }
    app.chats = response.data.chats;
    app.auth = true;
    app.sock = new WebSocket('ws://localhost:8000/websocket?user=' + Vue.cookies.get('user'));
    app.sock.onmessage = function (event) {
        message = JSON.parse(event.data);
        console.log(message);
        if (message.act === 'rmessage') {
            app.chats[message.receiver].messages[message.id].time = message.time;
        }
        if (message.act === 'sonline') {
            app.chats[message.user].online = true;
        }
        if (message.act === 'soffline') {
            app.chats[message.user].online = false;
        }
        if (message.act === 'imessage') {
            app.chats[message.from].messages.push({
                sender: message.from,
                text: message.text,
                time: message.time
            });
            if (app.current !== message.from) {
                app.chats[message.from].new = true;
            }
            else {
                app.$nextTick(function () {
                    updateScroll();
                });
            }
        }
        if (message.act === 'iregistered') {
            Vue.set(app.chats, message.user, {});
            Vue.set(app.chats[message.user], 'messages', []);
            Vue.set(app.chats[message.user], 'new', false);
            Vue.set(app.chats[message.user], 'online', false);
        }
    };
}

function updateScroll() {
    element = document.getElementById("mess");
    element.scrollTo(0, element.scrollHeight);
}