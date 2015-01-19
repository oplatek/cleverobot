var socket = io();
$('form').submit(function(){
    if (('#messages').lenght == 0) {
        socket.emit('begin', {'setup': 'unused'});
    }
    socket.emit('utterance', $('#m').val());
    $('#m').val('');
    return false;
});

socket.on('socketbot', function(msg){
    $('#messages').append($('<li class=".socketbot">').text(msg));
socket.on('utterance', function(msg){
    $('#messages').append($('<li class=".user">').text(msg));
});
