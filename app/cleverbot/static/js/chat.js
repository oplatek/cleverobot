$(document).ready(function() {
    var socket = io.connect();

    // TODO
    socket.on("connect", function() {
        console.log("Socket connected");
    });

    // TODO
    socket.on("connect_failed", function() {
        console.log("Unable to connect to the server.");
    });

    $('form').submit(function(){
        var utt_sended = $('#messages li').length;
        var msg = {'time': 'none', 'user':'human', 'utterance':$('#m').val()};
        console.log('Sending utterance[' + utt_sended +']: ' + msg)
        if(utt_sended == 0) {
            console.log('Beginning websocket connection')
            socket.emit('begin', {'setup': 'unused'});
        }
        console.log('Sending utterance ' + msg)
        socket.emit('utterance', msg);
        $('#m').val('');
        return false;
    });

    socket.on('socketbot', function(msg){
        console.log('Receiving msg' + msg);
        $('#messages').append($('<li class="socketbot">').text(msg.utterance));
    });
    socket.on('server_error', function(msg){
        console.log(msg);
        $('.content').append($('<div class="alert">').text('Status ' + msg.status + ': ' + msg.message));
    });
});
