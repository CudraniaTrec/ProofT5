/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

function sep1(rule, separator) {
  return seq(rule, repeat(seq(separator, rule)));
}

const DIGITS = token(choice('0', seq(/[1-9]/, optional(seq(optional('_'), sep1(/[0-9]+/, /_+/))))));
const DECIMAL_DIGITS = token(sep1(/[0-9]+/, '_'));

const PREC = {
  COMMENT: 0,         // //  /*  */
  ASSIGN: 1,          // =  += -=  *=  /=  %=  &=  ^=  |=  <<=  >>=  >>>=
  TERNARY: 3,         // ?:
  OR: 4,              // ||
  AND: 5,             // &&
  BIT_OR: 6,          // |
  BIT_XOR: 7,         // ^
  BIT_AND: 8,         // &
  EQUALITY: 9,        // ==  !=
  GENERIC: 10,
  REL: 10,            // <  <=  >  >=  instanceof
  SHIFT: 11,          // <<  >>  >>>
  ADD: 12,            // +  -
  MULT: 13,           // *  /  %
  CAST: 14,           // (Type)
  UNARY: 15,          // ++a  --a  a++  a--  +  -  !  ~
  METHOD_DECL: 16,    // method
  CLASS_DECL: 17,     // class
};

module.exports = grammar({
  name: 'dsl',

  extras: $ => [
    $.line_comment,
    $.block_comment,
    /[ \t\r\f\v]/,
  ],

  supertypes: $ => [
    // $.expression,
    // $.update_expression,
    // $.primary_expression,
    // $.statement,
    // $.local_variable_declaration,
    // $._literal,
    // $._type,
    // $._simple_type,
    // $.comment,
  ],

  inline: $ => [
    $._simple_type,
    $._class_body_declaration,
    $._variable_initializer,
  ],

  conflicts: $ => [
    [$._type, $.primary_expression],
    [$._type, $.generic_type],
    [$.generic_type, $.primary_expression],
  ],

  word: $ => $.identifier,

  rules: {
    program: $ => $.class_declaration,

    // Literals
    _literal: $ => choice(
      $.integer_literal,
      $.floating_point_literal,
      'true',
      'false',
      'null',
      $.character_literal,
      $.string_literal,
    ),

    integer_literal: _ => token(DIGITS),

    floating_point_literal: _ => token(choice(
      seq(DECIMAL_DIGITS, '.', optional(DECIMAL_DIGITS), optional(seq((/[eE]/), optional(choice('-', '+')), DECIMAL_DIGITS)), optional(/[fFdD]/)),
      seq('.', DECIMAL_DIGITS, optional(seq((/[eE]/), optional(choice('-', '+')), DECIMAL_DIGITS)), optional(/[fFdD]/)),
      seq(DIGITS, /[eEpP]/, optional(choice('-', '+')), DECIMAL_DIGITS, optional(/[fFdD]/)),
      seq(DIGITS, optional(seq((/[eE]/), optional(choice('-', '+')), DECIMAL_DIGITS)), (/[fFdD]/)),
    )),

    character_literal: _ => token(seq(
      '\'',
      repeat1(choice(
        /[^\\'\n]/,
        /\\./,
        /\\\n/,
      )),
      '\'',
    )),

    string_literal: $ => seq(
      '"',
      repeat(choice(
        $.string_fragment,
        $.escape_sequence,
      )),
      '"',
    ),

    string_fragment: _ => token.immediate(prec(1, /[^"\\]+/)),

    escape_sequence: _ => token.immediate(seq(
      '\\',
      choice(
        /[^xu0-7]/,
        /[0-7]{1,3}/,
        /x[0-9a-fA-F]{2}/,
        /u[0-9a-fA-F]{4}/,
        /u\{[0-9a-fA-F]+\}/,
      ))),

    // Types
    _type: $ => choice(
      $._simple_type,
      $.generic_type,
      $.array_type,
    ),

    _simple_type: $ => choice(
      'void',
      'int',
      'double',
      "bool",
      "char",
      "string",
      alias($.identifier, $.type_identifier),
    ),

    generic_type: $ => prec.dynamic(PREC.GENERIC, seq(
      $.identifier,
      choice(
        $.type_arguments0,
        $.type_arguments1,
        $.type_arguments2,
      ),
    )),
    
    type_arguments0: $ => seq('<', '>',),

    type_arguments1: $ => seq('<', $._type, '>'),

    type_arguments2: $ => seq('<', $._type, ',', $._type, '>'),

    array_type: $ => seq(
      field('element', $._type),
      field('dimensions', $.dimensions),
    ),

    dimensions: $ => prec.right(repeat1(seq('[', ']'))),

    // Expressions
    expression: $ => choice(
      $.assignment_expression,
      $.binary_expression,
      $.instanceof_expression,
      $.ternary_expression,
      $.update_expression,
      $.primary_expression,
      $.unary_expression,
      $.cast_expression,
    ),

    cast_expression: $ => prec(PREC.CAST, seq(
      '(', field('type', $._type), ')',
      field('value', $.expression),
    )),

    assignment_expression: $ => prec.right(PREC.ASSIGN, seq(
      field('left', choice(
        $.identifier,
        $.field_access,
        $.array_access,
      )),
      field('operator', ':='),
      field('right', $.expression),
    )),

    binary_expression: $ => choice(
      ...[
        ['>', PREC.REL],
        ['<', PREC.REL],
        ['>=', PREC.REL],
        ['<=', PREC.REL],
        ['==', PREC.EQUALITY],
        ['!=', PREC.EQUALITY],
        ['&&', PREC.AND],
        ['||', PREC.OR],
        ['+', PREC.ADD],
        ['-', PREC.ADD],
        ['*', PREC.MULT],
        ['/', PREC.MULT],
        ['&', PREC.BIT_AND],
        ['|', PREC.BIT_OR],
        ['^', PREC.BIT_XOR],
        ['%', PREC.MULT],
        ['<<', PREC.SHIFT],
        ['>>', PREC.SHIFT],
      ].map(([operator, precedence]) =>
        prec.left(precedence, seq(
          field('left', $.expression),
          field('operator', operator),
          field('right', $.expression),
        )),
      )),

    instanceof_expression: $ => prec(PREC.REL, seq(
      field('left', $.expression),
      'hasType',
      field('right', $._type),
    )),

    ternary_expression: $ => prec.right(PREC.TERNARY, seq(
      field('condition', $.expression),
      '?',
      field('consequence', $.expression),
      ':',
      field('alternative', $.expression),
    )),

    unary_expression: $ => choice(...[
      ['-', PREC.UNARY],
      ['!', PREC.UNARY],
      ['~', PREC.UNARY],
    ].map(([operator, precedence]) =>
      prec.left(precedence, seq(
        field('operator', operator),
        field('operand', $.expression),
      )),
    )),

    update_expression: $ => prec.left(PREC.UNARY, choice(
      $.post_inc,
      $.post_dec,
      $.pre_inc,
      $.pre_dec,
    )),

    post_inc: $ => prec.left(seq($.expression,'++')),

    post_dec: $ => prec.left(seq($.expression,'--')),

    pre_inc: $ => prec.right(seq('++', $.expression)),

    pre_dec: $ => prec.right(seq('--', $.expression)),

    primary_expression: $ => choice(
      $._literal,
      alias($.identifier, $.variable_identifier),
      $.parenthesized_expression,
      $.object_creation_expression,
      $.field_access,
      $.array_access,
      $.method_invocation,
      $.method_invocation_no_obj,
      $.array_creation_expression,
    ),

    parenthesized_expression: $ => seq('(', $.expression, ')'),

    object_creation_expression: $ => prec.right(seq(
      'new',
      field('type', choice($._simple_type, $.generic_type,)),
      field('arguments', $.argument_list)
    )),

    argument_list: $ => seq('(', optional($.term_list), ')'),
  
    term_list: $ => choice(
      $.expression,
      seq($.expression, ',', $.term_list),
    ),

    field_access: $ => seq(
      field('object', $.primary_expression),
      '.',
      field('field', $.identifier),
    ),

    array_access: $ => seq(
      field('array', $.primary_expression),
      '[', field('index', $.expression), ']',
    ),

    method_invocation: $ => seq(
      seq(
        field('object', $.primary_expression),
        '.',
        field('name', $.identifier),
      ),
      field('arguments', $.argument_list),
    ),

    method_invocation_no_obj: $ => seq(
      field('name', $.identifier),
      field('arguments', $.argument_list),
    ),

    array_creation_expression: $ => prec.right(seq(
      'new',
      field('type', choice($._simple_type, $.generic_type,)),
      field('dimensions', $.dimensions_exprs),
    )),

    dimensions_exprs: $ => prec.right(choice(
      seq('[', $.expression, ']'),
      seq('[', $.expression, ']', $.dimensions_exprs),
    )),

    // Statements
    statement: $ => choice(
      'skip',
      $.if_else_statement,
      $.if_statement,
      $.while_statement,
      $.do_statement,
      $.for_statement,
      $.enhanced_for_statement,
      $.break_statement,
      $.continue_statement,
      $.return_statement,
      $.local_variable_declaration,
      alias($.expression, $.expression_statement),
    ),

    statements: $ => prec.right(choice(
      $.statement,
      seq($.statement, ";", '\n', $.statements),
    )),

    do_statement: $ => seq(
      'do',
      field('body', $.statements), '\n',
      'end', 'do', '\n',
      'while', field('condition', $.parenthesized_expression)
    ),

    if_statement: $ => prec.right(seq(
      'if',
      field('condition', $.parenthesized_expression), '\n',
      field('consequence', $.statements), '\n',
      "end","if"
    )),

    if_else_statement: $ => prec.right(seq(
      'if',
      field('condition', $.parenthesized_expression), '\n',
      field('consequence', $.statements), '\n',
      'else', '\n',
      field('alternative', $.statements), '\n',
      "end","if"
    )),

    while_statement: $ => seq(
      'while',
      field('condition', $.parenthesized_expression), '\n',
      field('body', $.statements), '\n',
      "end","while"
    ),

    for_statement: $ => seq(
      'for', '(',
      field('init', $.local_variable_declaration), ';',
      field('condition', $.expression), ';',
      field('update', $.expression), ')', '\n',
      field('body', $.statements), '\n',
      "end","for"
    ),

    enhanced_for_statement: $ =>  seq(
      'foreach', '(', 
      field('type', $._type), field('name', $.identifier), 'in', field('array', $.expression), ')', '\n',
      field('body', $.statements), '\n',
      "end", "foreach"
    ),

    break_statement: $ => 'break',

    continue_statement: $ => 'continue',

    return_statement: $ => seq('return', $.expression),

    // Declarations
    class_declaration: $ => prec(PREC.CLASS_DECL, seq(
      'class',
      field('name', $.identifier), '\n',
      field('body', $.class_body), '\n',
      "end","class"
    )),

    modifiers: _ => seq('[', repeat1(choice('public','private','static',)), ']', '\n'),

    class_body: $ => repeat1($._class_body_declaration),

    _class_body_declaration: $ => $.method_declaration,

    method_declaration: $ => prec(PREC.METHOD_DECL, seq(
      field('modifiers', $.modifiers),
      field('name', $.identifier),
      field('parameters', $.formal_parameters),
      ':', field('type', $._type), '\n',
      field('body', $.statements), '\n',
      "end","method"
    )),

    local_variable_declaration: $ => choice(
      $.variable_declaration,
      $.variable_declaration_no_init,
    ),

    variable_declaration: $ => seq(
      field('name',$.identifier), ':', field('type', $._type),
      ':=', field('value', $._variable_initializer)
    ),

    variable_declaration_no_init: $ => seq(
      field('name',$.identifier), ':', field('type', $._type),
    ),

    _variable_initializer: $ => choice(
      $.expression,
      $.array_initializer,
    ),

    array_initializer: $ => seq('{', optional($.array_elements), '}'),

    array_elements: $ => choice(
      $._variable_initializer,
      seq($._variable_initializer, ',', $.array_elements),
    ),

    formal_parameters: $ => seq('(', optional($.formal_parameter_list), ')'),

    formal_parameter_list: $ => choice(
      $.local_variable_declaration,
      seq($.local_variable_declaration, ',', $.formal_parameter_list),
    ),

    //identifiers
    identifier: _ => /[\p{XID_Start}_$][\p{XID_Continue}\u00A2_$]*/,

    comment: $ => choice(
      $.line_comment,
      $.block_comment,
    ),

    line_comment: _ => token(prec(PREC.COMMENT, seq('//', /[^\n]*/))),

    block_comment: _ => token(prec(PREC.COMMENT,
      seq(
        '/*',
        /[^*]*\*+([^/*][^*]*\*+)*/,
        '/',
      ),
    )),
  },
});