$(document).ready( function () {
    $('table.display').DataTable({
    fixedHeader: {
        header: true,
        footer: true
    },
    paging: true,
    scrollCollapse: true,
    scrollY: '50vh',
    scrollX: true,
    scroller: true,
    dom: 'Bfrtip',
    paging: false,
    buttons: ['copy', 'csv', 'excel' ]
});
} );